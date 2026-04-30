"""Single source of truth for per-profile tool lists.

Add new tools here by importing them and appending to the appropriate profile list.
Cross-profile mixing is intentionally prevented — local tools must not appear in server and vice versa.
"""

from langchain_core.tools import BaseTool

from agent.tools.common import COMMON_TOOLS
from agent.tools.local import LOCAL_TOOLS
from agent.tools.server import SERVER_TOOLS

PROFILE_TOOLS: dict[str, list[BaseTool]] = {
    "local": COMMON_TOOLS + LOCAL_TOOLS,
    "server": COMMON_TOOLS + SERVER_TOOLS,
}


def get_tools(profile: str) -> list[BaseTool]:
    """Return the tool list for the given profile."""
    return PROFILE_TOOLS.get(profile, COMMON_TOOLS)
