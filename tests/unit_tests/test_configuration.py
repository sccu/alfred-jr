"""Tests for channel registry."""

from agent.channels.registry import get_channels
from agent.channels.teams import TeamsChannel
from agent.channels.telegram import TelegramChannel


def test_local_profile_returns_telegram_channel():
    channels = get_channels("local")
    assert len(channels) == 1
    assert isinstance(channels[0], TelegramChannel)


def test_server_profile_returns_teams_channel():
    channels = get_channels("server")
    assert len(channels) == 1
    assert isinstance(channels[0], TeamsChannel)


def test_unknown_profile_returns_empty():
    assert get_channels("staging") == []


def test_get_channels_returns_fresh_instances():
    a = get_channels("local")
    b = get_channels("local")
    assert a[0] is not b[0]
