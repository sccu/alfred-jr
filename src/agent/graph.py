"""LangGraph ReAct agent for Alfred Jr."""

from __future__ import annotations

import operator
from typing import Annotated

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from agent.config import ProfileSettings, load_settings
from agent.tools.registry import get_tools

_SYSTEM_PROMPT = "You are Alfred Jr., a helpful AI assistant."


class MessagesState(TypedDict):
    """Agent state — accumulates messages across nodes."""

    messages: Annotated[list[AnyMessage], operator.add]


def build_graph(settings: ProfileSettings):
    """Build and compile the LangGraph ReAct agent for the given profile settings."""
    tools = get_tools(settings.profile, settings)

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

    if tools:
        builder.add_node("tools", ToolNode(tools))
        builder.add_conditional_edges("llm_call", tools_condition)
        builder.add_edge("tools", "llm_call")
    else:
        builder.add_edge("llm_call", END)

    return builder.compile(name="alfred-jr")


# Module-level graph instance used by langgraph.json
graph = build_graph(load_settings())
