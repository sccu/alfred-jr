"""Telegram channel via python-telegram-bot webhook."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from agent.channels.base import BaseChannel
from agent.config import ProfileSettings
from agent.utils import extract_text


class TelegramChannel(BaseChannel):
    """Telegram webhook mounted at /telegram/webhook."""

    def __init__(self) -> None:
        self._ptb_app: Application | None = None
        self._webhook_url: str = ""

    def render(self, md: str) -> str:
        return md

    def mount(self, app: FastAPI, graph: CompiledStateGraph, settings: ProfileSettings) -> None:
        token = settings.telegram_bot_token
        if not token:
            logging.warning("TELEGRAM_BOT_TOKEN not set — Telegram channel disabled")
            return

        self._ptb_app = Application.builder().token(token).updater(None).build()
        self._webhook_url = f"{settings.tunnel_url}/telegram/webhook"

        from agent.history import ConversationHistory, build_detection_llm, detect_context_switch

        history = ConversationHistory()
        detection_llm = build_detection_llm(settings)

        async def _on_message(update: Update, _context) -> None:
            text = update.message.text if update.message else None
            if not text:
                return
            user_name = update.effective_user.full_name if update.effective_user else ""
            user_id = str(update.effective_chat.id)
            logging.info("[telegram] %s: %s", user_name or "unknown", text)
            try:
                user_history = history.get(user_id)
                if user_history:
                    try:
                        switched = await asyncio.wait_for(
                            detect_context_switch(detection_llm, user_history, text),
                            timeout=5,
                        )
                    except asyncio.TimeoutError:
                        switched = False
                    if switched:
                        logging.info("[telegram] context switch — history cleared for %s", user_id)
                        history.clear(user_id)
                        user_history = []
                result = await asyncio.wait_for(
                    graph.ainvoke(
                        {"messages": user_history + [HumanMessage(content=text)]},
                        config={"configurable": {"user_name": user_name, "response_format": "마크다운으로 응답"}},
                    ),
                    timeout=60,
                )
                ai_msg = result["messages"][-1]
                history.add(user_id, HumanMessage(content=text), ai_msg)
                reply = self.render(extract_text(ai_msg.content))
                await update.message.reply_text(reply)
            except Exception as e:
                logging.error("agent error: %s", e, exc_info=True)
                await update.message.reply_text("죄송합니다. 오류가 발생했습니다.")

        self._ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))

        @app.post("/telegram/webhook")
        async def telegram_webhook(request: Request) -> Response:
            """Receive Telegram Update and dispatch to PTB."""
            if "application/json" not in request.headers.get("content-type", ""):
                return Response(status_code=400)
            try:
                body = await request.json()
            except Exception:
                return Response(status_code=400)
            update = Update.de_json(body, self._ptb_app.bot)
            await self._ptb_app.process_update(update)
            return Response(status_code=200)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        if self._ptb_app is None:
            yield
            return
        await self._ptb_app.initialize()
        await self._ptb_app.bot.set_webhook(self._webhook_url)
        await self._ptb_app.start()
        logging.info("Telegram webhook set to %s", self._webhook_url)
        try:
            yield
        finally:
            await self._ptb_app.stop()
            await self._ptb_app.shutdown()
