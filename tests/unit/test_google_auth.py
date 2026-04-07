"""Tests for Google OAuth2 auth module."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "pepper" / "skills" / "google" / "scripts"))


def test_get_credentials_dir():
    """Credentials directory defaults to ~/.pepper/google/."""
    from auth import get_credentials_dir

    cred_dir = get_credentials_dir()
    assert cred_dir.name == "google"
    assert ".pepper" in str(cred_dir)


def test_get_token_path_env_override(tmp_path, monkeypatch):
    """PG_TOKEN_PATH env var overrides token location."""
    token_path = tmp_path / "token.json"
    monkeypatch.setenv("PG_TOKEN_PATH", str(token_path))

    from auth import get_token_path

    assert get_token_path() == token_path


def test_load_credentials_missing_token(tmp_path, monkeypatch):
    """Returns None when no token file exists."""
    monkeypatch.setenv("PG_TOKEN_PATH", str(tmp_path / "nonexistent.json"))

    from auth import load_credentials

    assert load_credentials() is None


def test_save_and_load_credentials(tmp_path, monkeypatch):
    """Credentials can be saved and loaded."""
    token_path = tmp_path / "token.json"
    monkeypatch.setenv("PG_TOKEN_PATH", str(token_path))

    mock_creds = MagicMock()
    mock_creds.to_json.return_value = json.dumps({
        "token": "access_123",
        "refresh_token": "refresh_456",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_id",
        "client_secret": "test_secret",
        "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
    })

    from auth import save_credentials

    save_credentials(mock_creds)
    assert token_path.exists()

    data = json.loads(token_path.read_text())
    assert data["token"] == "access_123"
    assert data["refresh_token"] == "refresh_456"


def test_auth_status_not_configured(tmp_path, monkeypatch):
    """auth_status returns not_configured when no token."""
    monkeypatch.setenv("PG_TOKEN_PATH", str(tmp_path / "nonexistent.json"))

    from auth import auth_status

    status = auth_status()
    assert status["status"] == "not_configured"
