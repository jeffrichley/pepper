"""SessionEnd hook: append transcript to daily log (with dedup).

1. Checks if this session was already logged by PreCompact
2. If not, appends transcript to daily/raw/YYYY-MM-DD.md with filelock
3. Returns empty JSON (session is ending, no systemMessage needed)

Env override: PEPPER_VAULT_PATH (for testing)
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from shared import (
    get_vault_path,
    append_to_daily_log,
    session_already_logged,
    read_stdin,
    write_stdout,
)


def main():
    hook_input = read_stdin()
    session_id = hook_input.get("session_id", "unknown")
    transcript_path = hook_input.get("transcript_path", "")

    vault_override = os.environ.get("PEPPER_VAULT_PATH")
    vault = Path(vault_override) if vault_override else get_vault_path()

    if transcript_path and Path(transcript_path).exists():
        if not session_already_logged(vault, session_id):
            transcript = Path(transcript_path).read_text(encoding="utf-8")
            append_to_daily_log(
                vault_path=vault,
                content=transcript,
                source="session-end",
                session_id=session_id,
            )

    write_stdout({})


if __name__ == "__main__":
    main()
