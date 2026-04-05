"""Spawn a short-lived Claude Code session with a prompt.

Hooks fire automatically (SessionStart injects Tier 1 context).
Used by heartbeat, reflection, and other scheduled tasks.
"""

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def spawn(prompt: str, append_context: str = "", timeout: int = 120) -> str:
    """Spawn a Claude Code session and return its text output.

    Args:
        prompt: The task for Claude to perform.
        append_context: Additional system prompt context (appended to default).
        timeout: Maximum seconds before killing the session.

    Returns:
        Claude's text response.

    Raises:
        RuntimeError: If the session exits with a non-zero code.
        subprocess.TimeoutExpired: If the session exceeds the timeout.
    """
    cmd = ["claude", "-p", prompt, "--output-format", "text"]
    if append_context:
        cmd += ["--append-system-prompt", append_context]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env={**os.environ},
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Spawn failed (exit {result.returncode}): {result.stderr}")
    return result.stdout


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: spawn_session.py 'prompt'")
        sys.exit(1)
    print(spawn(sys.argv[1]))
