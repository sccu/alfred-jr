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
    if settings.todoist_api_token:
        from agent.tools.todoist import create_todoist_tools

        tools.extend(create_todoist_tools(settings.todoist_api_token))
    if settings.gmail_credentials_path:
        from agent.tools.gmail import create_gmail_tools

        tools.extend(create_gmail_tools(settings.gmail_credentials_path))
    if settings.telegram_bot_token:
        from agent.tools.media import create_media_tools

        tools.extend(create_media_tools(settings.telegram_bot_token))
    return tools
