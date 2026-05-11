import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage
from agent.channels.base import BaseChannel

class MockChannel(BaseChannel):
    channel_name = "mock"
    def mount(self, app, graph, settings): pass
    def render(self, md): return f"rendered:{md}"

@pytest.mark.anyio
async def test_base_channel_handle_success():
    # Setup
    channel = MockChannel()
    graph = AsyncMock()
    # Mock graph response
    graph.ainvoke.return_value = {"messages": [AIMessage(content="Hello AI")]}
    
    # Execute
    result = await channel.handle(graph, "user123", "User Name", "Hi")
    
    # Verify
    assert result == "rendered:Hello AI"
    graph.ainvoke.assert_called_once()
    # Verify history was updated
    history = channel._history.get("user123")
    assert len(history) == 2
    assert isinstance(history[0], HumanMessage)
    assert isinstance(history[1], AIMessage)

@pytest.mark.anyio
async def test_base_channel_handle_error():
    # Setup
    channel = MockChannel()
    graph = AsyncMock()
    graph.ainvoke.side_effect = Exception("Graph failed")
    
    # Execute
    result = await channel.handle(graph, "user123", "User Name", "Hi")
    
    # Verify
    from agent.channels.base import _ERROR_REPLY
    assert result == _ERROR_REPLY
