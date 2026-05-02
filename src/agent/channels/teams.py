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

    def mount(self, app: FastAPI, graph: CompiledStateGraph, settings: ProfileSettings) -> None:
        adapter = BotFrameworkAdapter(
            BotFrameworkAdapterSettings(
                app_id=settings.bot_app_id,
                app_password=settings.bot_app_password,
                channel_auth_tenant=settings.bot_tenant_id or None,
            )
        )

        async def _handle(turn: TurnContext) -> None:
            if turn.activity.type == "message" and turn.activity.text:
                user_name = (
                    turn.activity.from_property.name
                    if turn.activity.from_property
                    else ""
                ) or ""
                try:
                    result = await asyncio.wait_for(
                        graph.ainvoke(
                            {"messages": [HumanMessage(content=turn.activity.text)]},
                            config={"configurable": {"user_name": user_name, "response_format": "일반 텍스트만 사용"}},
                        ),
                        timeout=30,
                    )
                    await turn.send_activity(extract_text(result["messages"][-1].content))
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
