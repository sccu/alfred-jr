"""FastAPI webhook server for Alfred Jr."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager, AsyncExitStack

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)

from agent.channels.registry import get_channels
from agent.config import ProfileSettings, load_settings
from agent.graph import build_graph


def _setup_langsmith(settings: ProfileSettings) -> None:
    if not settings.langsmith_api_key:
        return
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_TRACING"] = settings.langsmith_tracing
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    logging.info("LangSmith tracing enabled (project: %s)", settings.langsmith_project)


settings = load_settings()
_setup_langsmith(settings)
_graph = build_graph(settings)
_channels = get_channels(settings.profile)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        for ch in _channels:
            await stack.enter_async_context(ch.lifespan(app))
        yield


app = FastAPI(title="Alfred Jr.", lifespan=_lifespan)

for _channel in _channels:
    _channel.mount(app, _graph, settings)


@app.get("/health")
async def health() -> dict:
    """Return service health and active profile."""
    return {"status": "ok", "profile": settings.profile}
