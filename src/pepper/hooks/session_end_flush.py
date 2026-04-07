"""SessionEnd hook: minimal session marker.

Does NOT dump the raw transcript. Any important context should have been
saved by the agent during the session (via pre-compact nudges or proactive
note-taking). The reflection job at 3 AM summarizes the day.

Env override: PEPPER_VAULT_PATH (for testing)
"""

import contextlib

from pepper.hooks.shared import (
    read_stdin,
    write_stdout,
)


def main() -> None:
    """Mark session end and acknowledge."""
    with contextlib.suppress(Exception):
        read_stdin()

    # Session is ending — nothing to inject, just acknowledge
    write_stdout({})


if __name__ == "__main__":
    main()
