"""Channel registry — maps profiles to their active channels."""

from __future__ import annotations

from agent.channels.base import BaseChannel
from agent.channels.teams import TeamsChannel
from agent.channels.telegram import TelegramChannel

PROFILE_CHANNELS: dict[str, list[BaseChannel]] = {
    "local": [TelegramChannel()],
    "server": [TeamsChannel()],
}


def get_channels(profile: str) -> list[BaseChannel]:
    """Return the channel list for a given profile."""
    return PROFILE_CHANNELS.get(profile, [])
