"""LangGraph ReAct agent for Alfred Jr."""

from __future__ import annotations

import json
import logging
import operator
import zoneinfo
from datetime import datetime
from typing import Annotated

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from agent.config import ProfileSettings, load_settings
from agent.tools.registry import get_tools

_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
_TZ = zoneinfo.ZoneInfo("Asia/Seoul")

_PROFILE_DESC = {
    "local": "로컬 맥북 — 맥북 제어 권한 있음",
    "server": "서버 — 사내 시스템 접근 가능, 서버 자체 제어 불가",
}


def _build_system_prompt(
    settings: ProfileSettings,
    tools: list[BaseTool],
    user_name: str,
    response_format: str,
) -> str:
    now = datetime.now(_TZ)
    weekday = _WEEKDAYS[now.weekday()]
    tool_list = ", ".join(t.name for t in tools) if tools else "없음"
    profile_desc = _PROFILE_DESC.get(settings.profile, settings.profile)

    lines = [
        "당신은 Alfred Jr.입니다. 간결하고 실용적인 AI 어시스턴트입니다.",
        "사용자가 쓴 언어로 답변하세요.",
        "",
        "## 현재 컨텍스트",
        f"- 날짜·시각: {now.strftime('%Y-%m-%d')} ({weekday}) {now.strftime('%H:%M')} KST",
        "- 타임존: Asia/Seoul (UTC+9)",
        f"- 실행 환경: {profile_desc}",
        f"- 사용 가능한 도구: {tool_list}",
        "",
        "## 웹 검색 지침",
        "시점에 따라 답이 달라지는 질문(현재 상태, 최신 정보, 인물의 현직 등)을 검색할 때,"
        f" 질문에 시점 정보가 없으면 현재 날짜({now.strftime('%Y년 %m월 %d일')})를 쿼리에 포함하라.",
    ]
    if user_name:
        lines.append(f"- 사용자: {user_name}")
    if response_format:
        lines.append(f"- 응답 형식: {response_format}")

    return "\n".join(lines)


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
        thinking_budget=4096,
    )
    model = llm.bind_tools(tools) if tools else llm

    async def llm_call(state: MessagesState, config: RunnableConfig) -> dict:
        cfg = config.get("configurable", {})
        prompt = _build_system_prompt(
            settings,
            tools,
            user_name=cfg.get("user_name", ""),
            response_format=cfg.get("response_format", ""),
        )
        response = await model.ainvoke(
            [SystemMessage(content=prompt)] + state["messages"]
        )
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("llm_call", llm_call)
    builder.add_edge(START, "llm_call")

    if tools:
        _tool_node = ToolNode(tools)

        async def logged_tools(state: MessagesState) -> dict:
            last = state["messages"][-1]
            for tc in getattr(last, "tool_calls", []):
                logging.info("[tool] %s args=%s", tc["name"], json.dumps(tc.get("args", {}), ensure_ascii=False))
            result = await _tool_node.ainvoke(state)
            for msg in result.get("messages", []):
                if getattr(msg, "status", None) == "error":
                    logging.error("[tool:error] %s — %s", getattr(msg, "name", "unknown"), msg.content)
                    continue
                raw = getattr(msg, "content", None)
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and "url" in item:
                                logging.info("[tool:search] %s — %s", item["url"], item.get("title", ""))
                except (json.JSONDecodeError, TypeError):
                    pass
            return result

        builder.add_node("tools", logged_tools)
        builder.add_conditional_edges("llm_call", tools_condition)
        builder.add_edge("tools", "llm_call")
    else:
        builder.add_edge("llm_call", END)

    return builder.compile(name="alfred-jr")


# Module-level instance for the LangGraph CLI (langgraph.json) only.
# server.py calls build_graph() independently with its own settings.
graph = build_graph(load_settings())
