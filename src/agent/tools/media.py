"""Media tools — image sending via Telegram."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool

from agent.tools.local import _IMAGE_SUFFIXES, _is_sensitive

_MAX_PHOTO_BYTES = 10 * 1024 * 1024  # Telegram photo limit


def create_media_tools(telegram_token: str) -> list[BaseTool]:
    """Return media tools bound to the given Telegram bot token."""

    @tool
    def send_image(path: str, config: RunnableConfig) -> str:
        """로컬 이미지 파일을 현재 채팅에 전송한다. jpg, jpeg, png, gif, webp, bmp를 지원한다."""
        import httpx

        try:
            p = Path(path).expanduser().resolve()
            if _is_sensitive(p):
                return f"접근 거부: 민감한 경로입니다 — {path}"
            if not p.exists():
                return f"파일 없음: {path}"
            if p.suffix.lower() not in _IMAGE_SUFFIXES:
                return f"지원하지 않는 형식: {p.suffix}"
            if p.stat().st_size > _MAX_PHOTO_BYTES:
                return f"파일 크기 초과 (최대 10MB)"

            chat_id = (config.get("configurable") or {}).get("user_id", "")
            if not chat_id:
                return "이미지 전송 실패: chat_id를 찾을 수 없습니다"

            url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    url,
                    data={"chat_id": chat_id},
                    files={"photo": (p.name, p.read_bytes())},
                )
            if resp.status_code == 200:
                logging.info("[media] 이미지 전송: %s → %s", p.name, chat_id)
                return f"이미지 전송 완료: {p.name}"
            logging.error("[media] 전송 실패 %s: %s", resp.status_code, resp.text)
            return f"이미지 전송 실패: {resp.status_code}"
        except Exception as e:
            logging.error("[media] send_image 실패: %s", e, exc_info=True)
            return f"전송 실패: {e}"

    return [send_image]
