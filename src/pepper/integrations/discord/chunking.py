"""Paragraph-aware message chunking for Discord.

Splits long messages at natural boundaries (paragraphs, lines, spaces)
instead of hard character cuts. No chunk exceeds Discord's 2000-char limit.
"""

from __future__ import annotations

DISCORD_MSG_LIMIT = 2000


def smart_chunk(text: str, limit: int = DISCORD_MSG_LIMIT) -> list[str]:
    """Split text into chunks that respect natural boundaries.

    Priority order for split points:
    1. Paragraph boundary (double newline)
    2. Line boundary (single newline)
    3. Space
    4. Hard character cut (last resort)

    Args:
        text: The text to split.
        limit: Maximum characters per chunk (default 2000).

    Returns:
        List of text chunks, each within the limit.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        # Find the best split point within the limit
        split_at = _find_split_point(remaining, limit)
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip("\n")

    return chunks


def _find_split_point(text: str, limit: int) -> int:
    """Find the best place to split text within the character limit.

    Searches backwards from the limit for natural boundaries.
    """
    window = text[:limit]

    # Try paragraph boundary (double newline)
    pos = window.rfind("\n\n")
    if pos > 0:
        return pos + 1  # Include one newline, strip the rest

    # Try line boundary (single newline)
    pos = window.rfind("\n")
    if pos > 0:
        return pos + 1

    # Try space
    pos = window.rfind(" ")
    if pos > 0:
        return pos + 1

    # Hard cut — no natural boundary found
    return limit
