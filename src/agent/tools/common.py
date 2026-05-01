"""Tools available in all profiles."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from agent.config import ProfileSettings


def get_common_tools(settings: ProfileSettings) -> list[BaseTool]:
    """Build common tools from settings; gracefully skips tools with missing keys."""
    tools: list[BaseTool] = []
    if settings.tavily_api_key:
        from langchain_tavily import TavilySearch

        tools.append(TavilySearch(tavily_api_key=settings.tavily_api_key, max_results=5))
    return tools
