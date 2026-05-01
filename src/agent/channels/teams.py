"""Microsoft Teams channel via Bot Framework."""

from __future__ import annotations

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
                result = await graph.ainvoke(
                    {"messages": [HumanMessage(content=turn.activity.text)]}
                )
                await turn.send_activity(extract_text(result["messages"][-1].content))

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
                logging.error("process_activity failed: %s", e, exc_info=True)
                return Response(status_code=401)
            return Response(status_code=200)
