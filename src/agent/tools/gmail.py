"""Gmail tools via LangChain Gmail Toolkit."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from langchain_core.tools import BaseTool

_SCOPES = ["https://mail.google.com/"]


def create_gmail_tools(credentials_path: str) -> list[BaseTool]:
    """Return Gmail tools authenticated via OAuth.

    credentials_path: path to credentials.json (Google Cloud OAuth client secret).
    token.json is stored alongside credentials.json after the first auth flow.
    Run scripts/gmail_auth.py once to complete the initial browser-based OAuth.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from langchain_google_community import GmailToolkit
        from langchain_google_community.gmail.utils import build_resource_service
    except ImportError as e:
        logging.error("[gmail] 필수 패키지 미설치: %s", e)
        return []

    try:
        token_path = str(Path(credentials_path).parent / "token.json")
        creds = None

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                Path(token_path).write_text(creds.to_json())
            else:
                logging.error("[gmail] token.json 없음 — scripts/gmail_auth.py로 먼저 인증하세요")
                return []

        service = build_resource_service(credentials=creds)
        return GmailToolkit(api_resource=service).get_tools()
    except Exception as e:
        logging.error("[gmail] 초기화 실패: %s", e, exc_info=True)
        return []
