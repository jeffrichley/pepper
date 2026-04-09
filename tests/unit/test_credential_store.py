"""Tests for the credential store."""

from pepper.credentials.models import Credential, CredentialSummary


def test_credential_fields():
    """Credential dataclass holds all fields."""
    cred = Credential(
        service="apex",
        username="jeff@example.com",
        password="secret",
        url="https://apex.example.com",
        notes="Test",
    )
    assert cred.service == "apex"
    assert cred.password == "secret"


def test_credential_summary_excludes_password():
    """CredentialSummary has no password field."""
    summary = CredentialSummary(service="apex", username="jeff@example.com")
    assert not hasattr(summary, "password")
