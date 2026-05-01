"""Single source of truth for per-profile tool lists."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from agent.config import ProfileSettings
from agent.tools.common import get_common_tools
from agent.tools.local import LOCAL_TOOLS
from agent.tools.server import SERVER_TOOLS

_PROFILE_STATIC_TOOLS: dict[str, list[BaseTool]] = {
    "local": LOCAL_TOOLS,
    "server": SERVER_TOOLS,
}


def get_tools(profile: str, settings: ProfileSettings) -> list[BaseTool]:
    """Return the full tool list for the given profile."""
    return get_common_tools(settings) + _PROFILE_STATIC_TOOLS.get(profile, [])
