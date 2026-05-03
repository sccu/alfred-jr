"""Microsoft Teams channel via Bot Framework."""

from __future__ import annotations

import asyncio
import logging

from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity
from fastapi import FastAPI, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from agent.channels.base import BaseChannel
from agent.config import ProfileSettings
from agent.utils import extract_text


class TeamsChannel(BaseChannel):
    """Bot Framework adapter mounted at /api/messages."""

    def render(self, md: str) -> str:
        """Teams natively renders markdown — pass through as-is."""
        return md

    def mount(self, app: FastAPI, graph: CompiledStateGraph, settings: ProfileSettings) -> None:
        adapter = BotFrameworkAdapter(
            BotFrameworkAdapterSettings(
                app_id=settings.bot_app_id,
                app_password=settings.bot_app_password,
                channel_auth_tenant=settings.bot_tenant_id or None,
            )
        )

        from agent.history import ConversationHistory, build_detection_llm, detect_context_switch

        history = ConversationHistory()
        detection_llm = build_detection_llm(settings)

        async def _handle(turn: TurnContext) -> None:
            if turn.activity.type == "message" and turn.activity.text:
                user_name = (
                    turn.activity.from_property.name
                    if turn.activity.from_property
                    else ""
                ) or ""
                user_id = turn.activity.from_property.id if turn.activity.from_property else turn.activity.conversation.id
                logging.info("[teams] %s: %s", user_name or "unknown", turn.activity.text)
                try:
                    user_history = history.get(user_id)
                    if user_history:
                        try:
                            switched = await asyncio.wait_for(
                                detect_context_switch(detection_llm, user_history, turn.activity.text),
                                timeout=5,
                            )
                        except asyncio.TimeoutError:
                            switched = False
                        if switched:
                            logging.info("[teams] context switch — history cleared for %s", user_id)
                            history.clear(user_id)
                            user_history = []
                    result = await asyncio.wait_for(
                        graph.ainvoke(
                            {"messages": user_history + [HumanMessage(content=turn.activity.text)]},
                            config={"configurable": {"user_name": user_name, "response_format": "마크다운으로 응답"}},
                        ),
                        timeout=60,
                    )
                    ai_msg = result["messages"][-1]
                    history.add(user_id, HumanMessage(content=turn.activity.text), ai_msg)
                    reply = self.render(extract_text(ai_msg.content))
                    await turn.send_activity(Activity(type="message", text=reply, text_format="markdown"))
                except Exception as e:
                    logging.error("agent error: %s", e, exc_info=True)
                    await turn.send_activity("죄송합니다. 오류가 발생했습니다.")

        @app.post("/api/messages")
        async def messages(request: Request) -> Response:
            """Receive Teams Activity, invoke agent, send reply."""
            if "application/json" not in request.headers.get("content-type", ""):
                return Response(status_code=415)
            body = await request.json()
            activity = Activity().deserialize(body)
            auth_header = request.headers.get("Authorization", "")
            try:
                await adapter.process_activity(activity, auth_header, _handle)
            except Exception as e:
                logging.error("auth/framework error: %s", e, exc_info=True)
                return Response(status_code=401)
            return Response(status_code=200)
