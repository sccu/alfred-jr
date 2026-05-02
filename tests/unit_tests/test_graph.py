"""Tests for the LangGraph agent."""

import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from agent.config import ProfileSettings
from agent.graph import build_graph


def make_settings(**kwargs) -> ProfileSettings:
    defaults = {
        "gemini_api_key": "test-key",
        "bot_app_id": "app-id",
        "bot_app_password": "app-pass",
    }
    return ProfileSettings(_env_file=None, **{**defaults, **kwargs})


@pytest.mark.anyio
async def test_graph_returns_ai_message():
    settings = make_settings(profile="local")
    mock_response = AIMessage(content="Hello!")
    with patch("agent.graph.ChatGoogleGenerativeAI") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.bind_tools.return_value = mock_instance
        mock_instance.ainvoke = AsyncMock(return_value=mock_response)

        compiled = build_graph(settings)
        result = await compiled.ainvoke({"messages": [HumanMessage(content="Hi")]})

    assert isinstance(result["messages"][-1], AIMessage)


@pytest.mark.anyio
async def test_graph_local_and_server_build():
    for profile in ("local", "server"):
        settings = make_settings(profile=profile)
        compiled = build_graph(settings)
        assert compiled.name == "alfred-jr"
