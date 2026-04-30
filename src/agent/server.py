"""FastAPI webhook server for Microsoft Teams Bot Framework."""

from __future__ import annotations

from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity
from fastapi import FastAPI, Request, Response
from langchain_core.messages import HumanMessage

from agent.config import load_settings
from agent.graph import build_graph

settings = load_settings()
_graph = build_graph(settings)

_adapter = BotFrameworkAdapter(
    BotFrameworkAdapterSettings(
        app_id=settings.bot_app_id,
        app_password=settings.bot_app_password,
    )
)

app = FastAPI(title="Alfred Jr.")


@app.get("/health")
async def health() -> dict:
    """Return service health and active profile."""
    return {"status": "ok", "profile": settings.profile}


@app.post("/api/messages")
async def messages(request: Request) -> Response:
    """Receive Teams Activity, invoke agent, send reply."""
    if "application/json" not in request.headers.get("content-type", ""):
        return Response(status_code=415)

    body = await request.json()
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    async def _handle(turn: TurnContext) -> None:
        if turn.activity.type == "message" and turn.activity.text:
            result = await _graph.ainvoke(
                {"messages": [HumanMessage(content=turn.activity.text)]}
            )
            reply_text = result["messages"][-1].content
            await turn.send_activity(reply_text)

    try:
        await _adapter.process_activity(activity, auth_header, _handle)
    except Exception:
        return Response(status_code=401)

    return Response(status_code=200)
