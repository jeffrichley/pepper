"""Configuration for the Pepper Discord bot."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the bot directory
load_dotenv(Path(__file__).parent / ".env")

DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_URL: str = os.environ.get("PEPPER_CHANNEL_URL", "http://localhost:8788")

if not DISCORD_BOT_TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN is not set. "
        "Copy .env.example to .env and add your bot token."
    )
