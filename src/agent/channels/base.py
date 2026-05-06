"""Abstract base class for all channel adapters."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Awaitable, Callable

from fastapi import FastAPI
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from agent.config import ProfileSettings
from agent.history import ConversationHistory
from agent.utils import extract_text

_AGENT_TIMEOUT = 60
_ERROR_REPLY = "죄송합니다. 오류가 발생했습니다."


class BaseChannel(ABC):
    """Mounts channel-specific routes and manages lifecycle on the FastAPI app."""

    channel_name: str = "unknown"

    def __init__(self) -> None:
        self._history = ConversationHistory()

    @abstractmethod
    def mount(self, app: FastAPI, graph: CompiledStateGraph, settings: ProfileSettings) -> None:
        """Register routes on the app. Called before app startup."""

    @abstractmethod
    def render(self, md: str) -> str:
        """Convert Markdown to channel-native format."""

    async def handle(
        self,
        graph: CompiledStateGraph,
        user_id: str,
        user_name: str,
        text: str,
        send_reply: Callable[[str], Awaitable[Any]],
    ) -> None:
        """Log the incoming message, invoke the agent, and dispatch the reply."""
        logging.info("[%s] %s: %s", self.channel_name, user_name or "unknown", text)
        try:
            user_history = self._history.get(user_id)
            result = await asyncio.wait_for(
                graph.ainvoke(
                    {"messages": user_history + [HumanMessage(content=text)]},
                    config={"configurable": {"user_id": user_id, "user_name": user_name, "response_format": "마크다운으로 응답"}},
                ),
                timeout=_AGENT_TIMEOUT,
            )
            ai_msg = result["messages"][-1]
            self._history.add(user_id, HumanMessage(content=text), ai_msg)
            await send_reply(self.render(extract_text(ai_msg.content)))
        except Exception as e:
            logging.error("agent error: %s", e, exc_info=True)
            await send_reply(_ERROR_REPLY)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        """Override to add startup/shutdown logic. Default is a no-op."""
        yield
