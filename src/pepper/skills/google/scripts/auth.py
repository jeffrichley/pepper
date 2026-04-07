"""OAuth2 authentication for Google APIs.

Handles the installed app OAuth2 flow, token storage at ~/.pepper/google/,
and automatic token refresh.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Default scopes — expanded as new services are added
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_credentials_dir() -> Path:
    """Get the credentials directory (~/.pepper/google/)."""
    return Path.home() / ".pepper" / "google"


def get_token_path() -> Path:
    """Get the token file path, respecting PG_TOKEN_PATH env var."""
    env_path = os.environ.get("PG_TOKEN_PATH")
    if env_path:
        return Path(env_path)
    return get_credentials_dir() / "token.json"


def get_client_secret_path() -> Path:
    """Get the client_secret.json path, respecting PG_CLIENT_SECRET env var."""
    env_path = os.environ.get("PG_CLIENT_SECRET")
    if env_path:
        return Path(env_path)
    return get_credentials_dir() / "client_secret.json"


def load_credentials() -> Credentials | None:
    """Load saved credentials from token.json.

    Returns None if no token file exists.
    Attempts to refresh expired tokens automatically.
    """
    token_path = get_token_path()
    if not token_path.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
        except Exception:
            return None

    if creds and creds.valid:
        return creds

    return None


def save_credentials(creds: Credentials) -> None:
    """Save credentials to token.json."""
    token_path = get_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())


def login() -> Credentials:
    """Run the OAuth2 installed app flow.

    Opens a browser for user consent and saves the resulting token.
    """
    client_secret = get_client_secret_path()
    if not client_secret.exists():
        print(
            f"Error: client_secret.json not found at {client_secret}", file=sys.stderr
        )
        print(
            "Copy your Google Cloud OAuth2 credentials to that location.",
            file=sys.stderr,
        )
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=8080)
    save_credentials(creds)
    return creds


def get_credentials() -> Credentials:
    """Get valid credentials, prompting login if needed."""
    creds = load_credentials()
    if creds:
        return creds

    print("Not authenticated. Run: pg auth login", file=sys.stderr)
    sys.exit(1)


def auth_status() -> dict:
    """Check authentication status."""
    token_path = get_token_path()
    if not token_path.exists():
        return {
            "status": "not_configured",
            "message": "No token found. Run: pg auth login",
        }

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except Exception as e:
        return {"status": "error", "message": f"Invalid token: {e}"}

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return {
                "status": "authenticated",
                "scopes": list(creds.scopes or []),
                "message": "Token refreshed",
            }
        except Exception as e:
            return {
                "status": "expired",
                "message": f"Token expired and refresh failed: {e}",
            }

    if creds.valid:
        return {
            "status": "authenticated",
            "scopes": list(creds.scopes or []),
            "message": "Authenticated",
        }

    return {"status": "unknown", "message": "Token exists but state unclear"}
