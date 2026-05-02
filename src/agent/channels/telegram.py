"""Telegram channel via python-telegram-bot webhook."""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, MessageHandler, filters

from agent.channels.base import BaseChannel
from agent.config import ProfileSettings
from agent.utils import extract_text


_MDV2_SPECIAL = re.compile(r'([\\\_\*\[\]\(\)~`>#+\-=|{}.!])')


def _escape_mdv2(text: str) -> str:
    """Escape plain text for MarkdownV2."""
    return _MDV2_SPECIAL.sub(r'\\\1', text)


def _table_to_mdv2(table_lines: list[str]) -> str:
    """Convert markdown table to a MarkdownV2 code block."""
    rows = []
    for line in table_lines:
        if re.match(r'^[\s|:=-]+$', line):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        rows.append(cells)

    if not rows:
        return ''

    n_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < n_cols:
            r.append('')

    widths = [max(len(r[c]) for r in rows) for c in range(n_cols)]

    out = []
    for j, row in enumerate(rows):
        out.append('| ' + ' | '.join(row[c].ljust(widths[c]) for c in range(n_cols)) + ' |')
        if j == 0:
            out.append('|-' + '-+-'.join('-' * widths[c] for c in range(n_cols)) + '-|')

    return '```\n' + '\n'.join(out) + '\n```'


def _inline_mdv2(text: str) -> str:
    """Convert inline Markdown to MarkdownV2, escaping plain text."""
    result = []
    last = 0

    for m in re.finditer(r'\*\*(.+?)\*\*|__(.+?)__|`(.+?)`|\*(.+?)\*|(?<!\w)_(.+?)_(?!\w)', text):
        result.append(_escape_mdv2(text[last:m.start()]))
        g1, g2, g3, g4, g5 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if g1 is not None or g2 is not None:
            result.append('*' + _escape_mdv2(g1 or g2) + '*')
        elif g3 is not None:
            result.append('`' + g3 + '`')
        else:
            result.append('_' + _escape_mdv2(g4 or g5) + '_')
        last = m.end()

    result.append(_escape_mdv2(text[last:]))
    return ''.join(result)


def _render_markdownv2(text: str) -> str:
    """Convert Markdown to Telegram MarkdownV2."""
    lines = text.split('\n')
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code block
        if line.startswith('```'):
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code_lines.append(lines[i])
                i += 1
            code = '\n'.join(code_lines)
            result.append(f'```{lang}\n{code}\n```' if lang else f'```\n{code}\n```')
            i += 1
            continue

        # Table
        if '|' in line and i + 1 < len(lines) and re.match(r'^[\s|:=-]+$', lines[i + 1]):
            table_lines = []
            while i < len(lines) and '|' in lines[i]:
                table_lines.append(lines[i])
                i += 1
            result.append(_table_to_mdv2(table_lines))
            continue

        # Heading
        m = re.match(r'^#{1,6}\s+(.+)$', line)
        if m:
            result.append('*' + _escape_mdv2(m.group(1)) + '*')
            i += 1
            continue

        result.append(_inline_mdv2(line))
        i += 1

    return '\n'.join(result)


class TelegramChannel(BaseChannel):
    """Telegram webhook mounted at /telegram/webhook."""

    def __init__(self) -> None:
        self._ptb_app: Application | None = None
        self._webhook_url: str = ""

    def render(self, md: str) -> str:
        """Convert Markdown to Telegram MarkdownV2."""
        return _render_markdownv2(md)

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
            logging.info("[telegram] %s: %s", user_name or "unknown", text)
            try:
                result = await asyncio.wait_for(
                    graph.ainvoke(
                        {"messages": [HumanMessage(content=text)]},
                        config={"configurable": {"user_name": user_name, "response_format": "마크다운으로 응답"}},
                    ),
                    timeout=30,
                )
                reply = self.render(extract_text(result["messages"][-1].content))
                await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN_V2)
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
