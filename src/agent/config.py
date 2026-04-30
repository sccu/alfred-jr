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
    # Required by server.py for Bot Framework auth; optional during local graph-only use
    bot_app_id: str = ""
    bot_app_password: str = ""

    # local only
    tunnel_url: str = ""

    # server only
    internal_api_base_url: str = ""

    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")


def load_settings() -> ProfileSettings:
    """Load settings from .env.<profile>, falling back to .env if not found."""
    profile = os.getenv("PROFILE", "local")
    env_file = f".env.{profile}"
    if not os.path.exists(env_file):
        env_file = ".env"
    return ProfileSettings(_env_file=env_file)
