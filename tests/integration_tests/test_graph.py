"""Integration test: graph invocation with real Gemini (requires GEMINI_API_KEY)."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent.config import ProfileSettings
from agent.graph import build_graph

pytestmark = pytest.mark.anyio


@pytest.mark.langsmith
async def test_agent_returns_ai_message() -> None:
    settings = ProfileSettings(
        _env_file=None,
        gemini_api_key=__import__("os").environ["GEMINI_API_KEY"],
    )
    compiled = build_graph(settings)
    result = await compiled.ainvoke({"messages": [HumanMessage(content="Say hello.")]})
    assert isinstance(result["messages"][-1], AIMessage)
    assert result["messages"][-1].content
