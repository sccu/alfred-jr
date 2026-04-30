"""Tests for ProfileSettings."""

import pytest
from pydantic import ValidationError

from agent.config import ProfileSettings


def make_settings(overrides: dict) -> ProfileSettings:
    base = {
        "gemini_api_key": "test-key",
        "bot_app_id": "app-id",
        "bot_app_password": "app-pass",
    }
    return ProfileSettings(_env_file=None, **{**base, **overrides})


def test_default_profile_is_local():
    s = make_settings({})
    assert s.profile == "local"


def test_local_profile():
    s = make_settings({"profile": "local", "tunnel_url": "https://example.cfargotunnel.com"})
    assert s.profile == "local"
    assert s.tunnel_url == "https://example.cfargotunnel.com"
    assert s.internal_api_base_url == ""


def test_server_profile():
    s = make_settings({"profile": "server", "internal_api_base_url": "https://internal.corp"})
    assert s.profile == "server"
    assert s.internal_api_base_url == "https://internal.corp"
    assert s.tunnel_url == ""


def test_missing_gemini_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        ProfileSettings(_env_file=None, bot_app_id="x", bot_app_password="x")


def test_invalid_profile_raises():
    with pytest.raises(ValidationError):
        make_settings({"profile": "staging"})
