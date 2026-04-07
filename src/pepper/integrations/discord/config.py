"""Configuration for the Pepper Discord integration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the bot directory
INTEGRATION_DIR = Path(__file__).parent
load_dotenv(INTEGRATION_DIR / ".env")

DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_URL: str = os.environ.get("PEPPER_CHANNEL_URL", "http://localhost:8788")
SCHEDULER_DB: str = os.environ.get(
    "PEPPER_SCHEDULER_DB",
    str(INTEGRATION_DIR / "scheduler.db"),
)
JOBS_YAML: Path = INTEGRATION_DIR / "jobs.yaml"
TIMEZONE: str = os.environ.get("PEPPER_TIMEZONE", "US/Eastern")

if not DISCORD_BOT_TOKEN:
    raise RuntimeError(
        "DISCORD_BOT_TOKEN is not set. "
        "Copy .env.example to .env and add your bot token."
    )
