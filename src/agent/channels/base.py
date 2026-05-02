"""Abstract base class for all channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from langgraph.graph.state import CompiledStateGraph

from agent.config import ProfileSettings


class BaseChannel(ABC):
    """Mounts channel-specific routes and manages lifecycle on the FastAPI app."""

    @abstractmethod
    def mount(self, app: FastAPI, graph: CompiledStateGraph, settings: ProfileSettings) -> None:
        """Register routes on the app. Called before app startup."""

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        """Override to add startup/shutdown logic. Default is a no-op."""
        yield
