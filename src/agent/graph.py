"""LangGraph Q&A agent for Alfred Jr."""

from __future__ import annotations

from typing import Annotated
import operator

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph, START
from typing_extensions import TypedDict

from agent.config import ProfileSettings, load_settings
from agent.tools.registry import get_tools

_SYSTEM_PROMPT = "You are Alfred Jr., a helpful AI assistant."


class MessagesState(TypedDict):
    """Agent state — accumulates messages across nodes."""

    messages: Annotated[list[AnyMessage], operator.add]


def build_graph(settings: ProfileSettings):
    """Build and compile the LangGraph agent for the given profile settings."""
    tools = get_tools(settings.profile)

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0,
    )
    model = llm.bind_tools(tools) if tools else llm

    async def llm_call(state: MessagesState) -> dict:
        response = await model.ainvoke(
            [SystemMessage(content=_SYSTEM_PROMPT)] + state["messages"]
        )
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("llm_call", llm_call)
    builder.add_edge(START, "llm_call")
    builder.add_edge("llm_call", END)
    return builder.compile(name="alfred-jr")


# Module-level graph instance used by langgraph.json
graph = build_graph(load_settings())
