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

    def mount(self, app: FastAPI, graph: CompiledStateGraph, settings: ProfileSettings) -> None:
        token = settings.telegram_bot_token
        if not token:
            logging.warning("TELEGRAM_BOT_TOKEN not set — Telegram channel disabled")
            return

        self._ptb_app = Application.builder().token(token).updater(None).build()
        self._webhook_url = f"{settings.tunnel_url}/telegram/webhook"

        async def _on_message(update: Update, _context) -> None:
            text = update.message.text if update.message else None
            if not text:
                return
            user_name = update.effective_user.full_name if update.effective_user else ""
            try:
                result = await asyncio.wait_for(
                    graph.ainvoke(
                        {"messages": [HumanMessage(content=text)]},
                        config={"configurable": {"user_name": user_name, "response_format": "마크다운 사용 가능"}},
                    ),
                    timeout=30,
                )
                reply = extract_text(result["messages"][-1].content)
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
