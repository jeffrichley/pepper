"""Pepper credential store — secure credential storage via KeePass.

Public API for credential operations. Used by the CLI and available
for direct import if needed elsewhere.
"""

from __future__ import annotations

from pathlib import Path

from pepper.credentials.models import Credential, CredentialSummary
from pepper.credentials.store import CredentialStore

__all__ = [
    "Credential",
    "CredentialSummary",
    "delete_credential",
    "get_credential",
    "list_credentials",
    "set_credential",
]

_DEFAULT_PATH = Path.home() / ".pepper" / "credentials.kdbx"


def get_credential(service: str) -> Credential | None:
    """Retrieve a credential by service name."""
    return CredentialStore(_DEFAULT_PATH).get(service)


def set_credential(
    service: str,
    username: str,
    password: str,
    url: str = "",
    notes: str = "",
) -> None:
    """Store or overwrite a credential."""
    CredentialStore(_DEFAULT_PATH).set(service, username, password, url, notes)


def list_credentials() -> list[CredentialSummary]:
    """List all stored credentials without passwords."""
    return CredentialStore(_DEFAULT_PATH).list()


def delete_credential(service: str) -> bool:
    """Delete a credential. Returns True if found and deleted."""
    return CredentialStore(_DEFAULT_PATH).delete(service)
