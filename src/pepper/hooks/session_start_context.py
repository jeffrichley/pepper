"""SessionStart hook: inject Tier 1 context into every Claude Code session."""

import contextlib
import json

from pepper.hooks.shared import (
    get_vault_path,
    read_recent_summaries,
    read_stdin,
    read_tier1_files,
    write_stdout,
)


def main() -> None:
    """Inject Tier 1 context into the Claude Code session."""
    with contextlib.suppress(json.JSONDecodeError, EOFError):
        read_stdin()

    vault = get_vault_path()

    tier1_content = read_tier1_files(vault)
    summaries = read_recent_summaries(vault, daily_count=2, include_weekly=True)

    parts = [tier1_content]
    if summaries:
        parts.append(summaries)

    system_message = "\n\n---\n\n".join(parts)
    write_stdout({"systemMessage": system_message})


if __name__ == "__main__":
    main()
