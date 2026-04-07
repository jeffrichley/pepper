"""PreCompact hook: save transcript to daily log and nudge Claude."""

from datetime import datetime
from pathlib import Path

from pepper.hooks.shared import (
    get_vault_path,
    append_to_daily_log,
    read_stdin,
    write_stdout,
)


def main():
    hook_input = read_stdin()
    session_id = hook_input.get("session_id", "unknown")
    transcript_path = hook_input.get("transcript_path", "")

    vault = get_vault_path()

    if transcript_path and Path(transcript_path).exists():
        transcript = Path(transcript_path).read_text(encoding="utf-8")
        append_to_daily_log(
            vault_path=vault,
            content=transcript,
            source="pre-compact",
            session_id=session_id,
        )

    today = datetime.now().strftime("%Y-%m-%d")
    write_stdout({
        "systemMessage": (
            "Context is about to be compacted. If you have any unsaved decisions, "
            "facts, or action items from this conversation, write them to the daily "
            f"log now using: Memory/daily/raw/{today}.md"
        )
    })


if __name__ == "__main__":
    main()
