"""Telegram channel via python-telegram-bot webhook."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

from agent.channels.base import BaseChannel
from agent.config import ProfileSettings


class TelegramChannel(BaseChannel):
    """Telegram webhook mounted at /telegram/webhook."""

    def mount(self, app: FastAPI, graph: CompiledStateGraph, settings: ProfileSettings) -> None:
        token = settings.telegram_bot_token
        if not token:
            logging.warning("TELEGRAM_BOT_TOKEN not set — Telegram channel disabled")
            return

        ptb_app = Application.builder().token(token).updater(None).build()

        async def _on_message(update: Update, _context) -> None:
            text = update.message.text if update.message else None
            if not text:
                return
            result = await graph.ainvoke({"messages": [HumanMessage(content=text)]})
            reply = result["messages"][-1].content
            await update.message.reply_text(reply)

        ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))

        @app.on_event("startup")
        async def _startup() -> None:
            await ptb_app.initialize()
            webhook_url = f"{settings.tunnel_url}/telegram/webhook"
            await ptb_app.bot.set_webhook(webhook_url)
            await ptb_app.start()
            logging.info("Telegram webhook set to %s", webhook_url)

        @app.on_event("shutdown")
        async def _shutdown() -> None:
            await ptb_app.stop()
            await ptb_app.shutdown()

        @app.post("/telegram/webhook")
        async def telegram_webhook(request: Request) -> Response:
            """Receive Telegram Update and dispatch to PTB."""
            body = await request.json()
            update = Update.de_json(body, ptb_app.bot)
            await ptb_app.process_update(update)
            return Response(status_code=200)
