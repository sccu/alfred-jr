"""FastAPI webhook server for Alfred Jr."""

from __future__ import annotations

import logging

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)

from agent.channels.registry import get_channels
from agent.config import load_settings
from agent.graph import build_graph

settings = load_settings()
_graph = build_graph(settings)

app = FastAPI(title="Alfred Jr.")

for _channel in get_channels(settings.profile):
    _channel.mount(app, _graph, settings)


@app.get("/health")
async def health() -> dict:
    """Return service health and active profile."""
    return {"status": "ok", "profile": settings.profile}
