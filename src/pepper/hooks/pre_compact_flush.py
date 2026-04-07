"""PreCompact hook: nudge Claude to save important context before compaction.

Does NOT dump the raw transcript — the agent decides what's worth keeping
and writes it to the daily log. The reflection job summarizes later.

Env override: PEPPER_VAULT_PATH (for testing)
"""

import contextlib
from datetime import datetime

from pepper.hooks.shared import (
    read_stdin,
    write_stdout,
)


def main() -> None:
    """Nudge Claude to save context before compaction."""
    with contextlib.suppress(Exception):
        read_stdin()

    today = datetime.now().strftime("%Y-%m-%d")
    write_stdout(
        {
            "systemMessage": (
                "Context is about to be compacted. If you have any unsaved decisions, "
                "facts, or action items from this conversation, "
                "write them to the daily "
                f"log now using: Memory/daily/raw/{today}.md"
            )
        }
    )


if __name__ == "__main__":
    main()
