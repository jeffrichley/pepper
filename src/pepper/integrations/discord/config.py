"""Configuration for the Pepper Discord integration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from runtime directory (~/.pepper/.env) first, then package dir.
# Environment variables set by pepper start take precedence over all .env files.
_runtime_env = Path.home() / ".pepper" / ".env"
if _runtime_env.exists():
    load_dotenv(_runtime_env)

INTEGRATION_DIR = Path(__file__).parent
load_dotenv(INTEGRATION_DIR / ".env")

DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_URL: str = os.environ.get("PEPPER_CHANNEL_URL", "http://localhost:8788")


def require_token() -> str:
    """Return the bot token, raising if not set. Call at bot startup, not import."""
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN is not set. "
            "Set it in ~/.pepper/.env or as an environment variable."
        )
    return DISCORD_BOT_TOKEN
