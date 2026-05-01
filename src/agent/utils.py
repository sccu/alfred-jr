"""Shared utilities for Alfred Jr."""

from __future__ import annotations


def extract_text(content: str | list) -> str:
    """Extract plain text from an AIMessage content (str or content-block list)."""
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "") if isinstance(block, dict) else str(block)
        for block in content
        if not isinstance(block, dict) or block.get("type") == "text"
    )
