"""Channel registry — maps profiles to their active channel classes."""

from __future__ import annotations

from agent.channels.base import BaseChannel
from agent.channels.teams import TeamsChannel
from agent.channels.telegram import TelegramChannel

_PROFILE_CHANNEL_CLASSES: dict[str, list[type[BaseChannel]]] = {
    "local": [TelegramChannel],
    "server": [TeamsChannel],
}


def get_channels(profile: str) -> list[BaseChannel]:
    """Return fresh channel instances for the given profile."""
    return [cls() for cls in _PROFILE_CHANNEL_CLASSES.get(profile, [])]
