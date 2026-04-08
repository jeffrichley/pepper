"""Configuration for the Pepper Scheduler."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from runtime directory (~/.pepper/.env) first.
_runtime_env = Path.home() / ".pepper" / ".env"
if _runtime_env.exists():
    load_dotenv(_runtime_env)

CHANNEL_URL: str = os.environ.get("PEPPER_CHANNEL_URL", "http://localhost:8788")
SCHEDULER_DB: str = os.environ.get(
    "PEPPER_SCHEDULER_DB",
    str(Path.home() / ".pepper" / "scheduler.db"),
)
JOBS_YAML: Path = Path(__file__).parent / "jobs.yaml"
TIMEZONE: str = os.environ.get("PEPPER_TIMEZONE", "US/Eastern")
