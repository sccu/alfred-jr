"""Profile-aware settings loaded from .env.local or .env.server."""

from __future__ import annotations

import os
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProfileSettings(BaseSettings):
    """Single source of truth for all environment-driven configuration."""

    profile: Literal["local", "server"] = "local"

    # Common
    gemini_api_key: str
    tavily_api_key: str = ""
    todoist_api_token: str = ""

    # LangSmith tracing (optional)
    langsmith_api_key: str = ""
    langsmith_tracing: str = "false"
    langsmith_project: str = "alfred-jr"
    # Required by server.py for Bot Framework auth; optional during local graph-only use
    bot_app_id: str = ""
    bot_app_password: str = ""
    # Single Tenant bot registration (required since Multi Tenant deprecated July 2025)
    bot_tenant_id: str = ""

    # local only
    telegram_bot_token: str = ""
    tunnel_url: str = ""

    # server only
    internal_api_base_url: str = ""

    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")


def load_settings() -> ProfileSettings:
    """Load settings from .env.<profile>, falling back to .env if not found."""
    # os.getenv is permitted here only: we need the profile value before ProfileSettings
    # can be constructed, so there is no alternative to reading it from the environment directly.
    profile = os.getenv("PROFILE", "local")
    env_file = f".env.{profile}"
    if not os.path.exists(env_file):
        env_file = ".env"
    return ProfileSettings(_env_file=env_file)
