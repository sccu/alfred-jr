"""Abstract base class for all channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import FastAPI
from langgraph.graph.state import CompiledStateGraph

from agent.config import ProfileSettings


class BaseChannel(ABC):
    """Mounts channel-specific routes or polling onto the FastAPI app."""

    @abstractmethod
    def mount(self, app: FastAPI, graph: CompiledStateGraph, settings: ProfileSettings) -> None:
        """Register routes or start background tasks on app."""
