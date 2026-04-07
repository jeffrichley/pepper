"""SessionStart hook: inject Tier 1 context into every Claude Code session."""

import json

from pepper.hooks.shared import (
    get_vault_path,
    read_tier1_files,
    read_recent_summaries,
    read_stdin,
    write_stdout,
)


def main():
    try:
        read_stdin()
    except (json.JSONDecodeError, EOFError):
        pass

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
