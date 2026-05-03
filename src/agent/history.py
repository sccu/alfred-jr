"""Per-user conversation history with context-switch detection."""

from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.config import ProfileSettings


class ConversationHistory:
    """In-memory sliding-window conversation history keyed by user ID."""

    def __init__(self, max_turns: int = 10) -> None:
        self.max_turns = max_turns
        self._store: dict[str, list[BaseMessage]] = {}

    def get(self, user_id: str) -> list[BaseMessage]:
        return list(self._store.get(user_id, []))

    def add(self, user_id: str, human: BaseMessage, ai: BaseMessage) -> None:
        msgs = self._store.setdefault(user_id, [])
        msgs.extend([human, ai])
        cap = self.max_turns * 2
        if len(msgs) > cap:
            self._store[user_id] = msgs[-cap:]

    def clear(self, user_id: str) -> None:
        self._store.pop(user_id, None)


def build_detection_llm(settings: ProfileSettings) -> ChatGoogleGenerativeAI:
    """Build a fast, no-thinking LLM instance for context-switch detection."""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0,
        thinking_budget=0,
    )


async def detect_context_switch(
    llm: ChatGoogleGenerativeAI,
    history: list[BaseMessage],
    new_message: str,
) -> bool:
    """Return True if new_message starts a new topic unrelated to history."""
    if not history:
        return False
    result = await llm.ainvoke(
        [SystemMessage(content=(
            "대화 맥락과 새 메시지를 비교해. "
            "새 메시지가 이전 대화와 완전히 관계없는 새 주제면 YES, 이어지는 대화면 NO만 답해."
        ))]
        + history[-4:]
        + [HumanMessage(content=new_message)]
    )
    return result.content.strip().upper().startswith("YES")
