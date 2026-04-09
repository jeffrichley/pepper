# Credential Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `pepper creds` CLI backed by pykeepass so Jeff can securely store credentials and Pepper can retrieve them in playbooks.

**Architecture:** A `credentials/` package with a pykeepass store wrapper, a public API module, and a Typer CLI subcommand group registered on the existing `pepper` app. A skill doc teaches Pepper how to use it. No MCP server.

**Tech Stack:** pykeepass (already installed), typer, rich, getpass

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/pepper/credentials/__init__.py` | Public API: `get_credential`, `set_credential`, `list_credentials`, `delete_credential` |
| `src/pepper/credentials/store.py` | pykeepass wrapper — open vault, CRUD, close |
| `src/pepper/credentials/models.py` | `Credential` and `CredentialSummary` dataclasses |
| `src/pepper/credentials/cli.py` | Typer subcommand group (`pepper creds init/set/get/list/delete`) |
| `src/pepper/cli.py` | Modified — register `creds_app` subcommand |
| `src/pepper/skills/creds/SKILL.md` | Skill doc for Pepper |
| `tests/unit/test_credential_store.py` | Tests for store.py |
| `tests/unit/test_credential_cli.py` | Tests for CLI commands |

---

### Task 1: Models

**Files:**
- Create: `src/pepper/credentials/__init__.py` (empty for now)
- Create: `src/pepper/credentials/models.py`
- Test: `tests/unit/test_credential_store.py`

- [ ] **Step 1: Create the package directory**

```bash
mkdir -p src/pepper/credentials
```

- [ ] **Step 2: Create empty `__init__.py`**

Create `src/pepper/credentials/__init__.py` with just the docstring:

```python
"""Pepper credential store — secure credential storage via KeePass."""
```

- [ ] **Step 3: Write the models**

Create `src/pepper/credentials/models.py`:

```python
"""Credential data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Credential:
    """A stored credential with all fields."""

    service: str
    username: str
    password: str
    url: str = ""
    notes: str = ""


@dataclass
class CredentialSummary:
    """A credential summary without the password."""

    service: str
    username: str
    url: str = ""
```

- [ ] **Step 4: Write a smoke test for models**

Create `tests/unit/test_credential_store.py`:

```python
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
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_credential_store.py -v`
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add src/pepper/credentials/ tests/unit/test_credential_store.py
git commit -m "feat(creds): add credential models"
```

---

### Task 2: Store — pykeepass wrapper

**Files:**
- Create: `src/pepper/credentials/store.py`
- Modify: `tests/unit/test_credential_store.py`

- [ ] **Step 1: Write failing tests for the store**

Append to `tests/unit/test_credential_store.py`:

```python
import os

import pytest

from pepper.credentials.models import Credential
from pepper.credentials.store import CredentialStore


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    """Create a temp vault with a known master password."""
    monkeypatch.setenv("PEPPER_VAULT_PASSWORD", "testpass")
    vault_path = tmp_path / "credentials.kdbx"
    return CredentialStore(vault_path)


def test_set_and_get(vault):
    """Store and retrieve a credential."""
    vault.set("apex", "jeff@test.com", "secret123", "https://apex.com", "notes")
    cred = vault.get("apex")
    assert cred is not None
    assert cred.service == "apex"
    assert cred.username == "jeff@test.com"
    assert cred.password == "secret123"
    assert cred.url == "https://apex.com"
    assert cred.notes == "notes"


def test_get_missing_returns_none(vault):
    """Getting a nonexistent service returns None."""
    assert vault.get("nonexistent") is None


def test_set_overwrites_existing(vault):
    """Setting a service that exists overwrites it."""
    vault.set("apex", "old@test.com", "old")
    vault.set("apex", "new@test.com", "new")
    cred = vault.get("apex")
    assert cred is not None
    assert cred.username == "new@test.com"
    assert cred.password == "new"


def test_list_credentials(vault):
    """List returns summaries without passwords."""
    vault.set("apex", "jeff@test.com", "secret1")
    vault.set("etsy", "jeff@etsy.com", "secret2", "https://etsy.com")
    summaries = vault.list()
    assert len(summaries) == 2
    names = {s.service for s in summaries}
    assert names == {"apex", "etsy"}
    # Summaries should not have password attribute content exposed
    for s in summaries:
        assert not hasattr(s, "password")


def test_delete_existing(vault):
    """Delete removes a credential and returns True."""
    vault.set("apex", "jeff@test.com", "secret")
    assert vault.delete("apex") is True
    assert vault.get("apex") is None


def test_delete_missing_returns_false(vault):
    """Delete on nonexistent service returns False."""
    assert vault.delete("nonexistent") is False


def test_creates_vault_on_first_set(vault, tmp_path):
    """The .kdbx file is created on first set if it doesn't exist."""
    vault_path = tmp_path / "credentials.kdbx"
    assert not vault_path.exists()
    vault.set("apex", "jeff@test.com", "secret")
    assert vault_path.exists()


def test_missing_password_env_raises(tmp_path, monkeypatch):
    """Store raises ValueError if PEPPER_VAULT_PASSWORD is not set."""
    monkeypatch.delenv("PEPPER_VAULT_PASSWORD", raising=False)
    store = CredentialStore(tmp_path / "credentials.kdbx")
    with pytest.raises(ValueError, match="PEPPER_VAULT_PASSWORD"):
        store.get("anything")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_credential_store.py -v`
Expected: FAIL — `cannot import name 'CredentialStore'`

- [ ] **Step 3: Implement the store**

Create `src/pepper/credentials/store.py`:

```python
"""KeePass credential store — pykeepass wrapper."""

from __future__ import annotations

import os
from pathlib import Path

from pykeepass import PyKeePass, create_database

from pepper.credentials.models import Credential, CredentialSummary


class CredentialStore:
    """CRUD operations on an encrypted KeePass vault.

    Each operation opens the vault, performs the action, and saves/closes.
    The master password comes from the PEPPER_VAULT_PASSWORD env var.

    Args:
        vault_path: Path to the .kdbx file. Created on first write.
    """

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path

    def _get_password(self) -> str:
        """Read the master password from the environment."""
        password = os.environ.get("PEPPER_VAULT_PASSWORD")
        if not password:
            msg = (
                "PEPPER_VAULT_PASSWORD environment variable is not set. "
                "Add it to ~/.pepper/.env"
            )
            raise ValueError(msg)
        return password

    def _open(self) -> PyKeePass:
        """Open the vault, creating it if it doesn't exist."""
        password = self._get_password()
        if not self.vault_path.exists():
            return create_database(str(self.vault_path), password=password)
        return PyKeePass(str(self.vault_path), password=password)

    def get(self, service: str) -> Credential | None:
        """Retrieve a credential by service name.

        Args:
            service: The service identifier (e.g. "apex").

        Returns:
            The credential, or None if not found.
        """
        kp = self._open()
        entry = kp.find_entries(title=service, first=True)
        if entry is None:
            return None
        return Credential(
            service=entry.title,
            username=entry.username or "",
            password=entry.password or "",
            url=entry.url or "",
            notes=entry.notes or "",
        )

    def set(
        self,
        service: str,
        username: str,
        password: str,
        url: str = "",
        notes: str = "",
    ) -> None:
        """Store or overwrite a credential.

        Args:
            service: The service identifier.
            username: Login username.
            password: Login password.
            url: Optional service URL.
            notes: Optional notes.
        """
        kp = self._open()
        existing = kp.find_entries(title=service, first=True)
        if existing:
            existing.username = username
            existing.password = password
            existing.url = url
            existing.notes = notes
        else:
            kp.add_entry(
                kp.root_group,
                title=service,
                username=username,
                password=password,
                url=url,
                notes=notes,
            )
        kp.save()

    def list(self) -> list[CredentialSummary]:
        """List all stored credentials without passwords.

        Returns:
            List of credential summaries.
        """
        kp = self._open()
        return [
            CredentialSummary(
                service=entry.title,
                username=entry.username or "",
                url=entry.url or "",
            )
            for entry in kp.entries
        ]

    def delete(self, service: str) -> bool:
        """Delete a credential by service name.

        Args:
            service: The service identifier.

        Returns:
            True if deleted, False if not found.
        """
        kp = self._open()
        entry = kp.find_entries(title=service, first=True)
        if entry is None:
            return False
        kp.delete_entry(entry)
        kp.save()
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_credential_store.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/pepper/credentials/store.py tests/unit/test_credential_store.py
git commit -m "feat(creds): add pykeepass credential store"
```

---

### Task 3: Public API

**Files:**
- Modify: `src/pepper/credentials/__init__.py`

- [ ] **Step 1: Write the public API**

Replace `src/pepper/credentials/__init__.py` with:

```python
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
```

- [ ] **Step 2: Verify imports work**

Run: `uv run python -c "from pepper.credentials import get_credential, set_credential, list_credentials, delete_credential; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/pepper/credentials/__init__.py
git commit -m "feat(creds): add public API module"
```

---

### Task 4: CLI subcommands

**Files:**
- Create: `src/pepper/credentials/cli.py`
- Modify: `src/pepper/cli.py`
- Create: `tests/unit/test_credential_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/unit/test_credential_cli.py`:

```python
"""Tests for pepper creds CLI commands."""

from typer.testing import CliRunner

from pepper.cli import app

runner = CliRunner()


def test_creds_set_and_get(tmp_path, monkeypatch):
    """Set a credential then get it back."""
    monkeypatch.setenv("PEPPER_VAULT_PASSWORD", "testpass")
    vault_path = tmp_path / "credentials.kdbx"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)

    result = runner.invoke(
        app,
        ["creds", "set", "apex"],
        input="jeff@test.com\nsecret123\nhttps://apex.com\nTest notes\n",
    )
    assert result.exit_code == 0
    assert "Saved" in result.output

    result = runner.invoke(app, ["creds", "get", "apex"])
    assert result.exit_code == 0
    assert "jeff@test.com" in result.output
    # Default mode should NOT show password
    assert "secret123" not in result.output


def test_creds_get_json(tmp_path, monkeypatch):
    """Get with --json includes password."""
    monkeypatch.setenv("PEPPER_VAULT_PASSWORD", "testpass")
    vault_path = tmp_path / "credentials.kdbx"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)

    runner.invoke(
        app,
        ["creds", "set", "apex"],
        input="jeff@test.com\nsecret123\n\n\n",
    )
    result = runner.invoke(app, ["creds", "get", "apex", "--json"])
    assert result.exit_code == 0
    assert "secret123" in result.output


def test_creds_get_not_found(tmp_path, monkeypatch):
    """Get nonexistent service exits with code 1."""
    monkeypatch.setenv("PEPPER_VAULT_PASSWORD", "testpass")
    vault_path = tmp_path / "credentials.kdbx"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)

    result = runner.invoke(app, ["creds", "get", "nonexistent"])
    assert result.exit_code == 1


def test_creds_list(tmp_path, monkeypatch):
    """List shows service names."""
    monkeypatch.setenv("PEPPER_VAULT_PASSWORD", "testpass")
    vault_path = tmp_path / "credentials.kdbx"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)

    runner.invoke(
        app,
        ["creds", "set", "apex"],
        input="jeff@test.com\nsecret\n\n\n",
    )
    runner.invoke(
        app,
        ["creds", "set", "etsy"],
        input="jeff@etsy.com\nsecret\n\n\n",
    )
    result = runner.invoke(app, ["creds", "list"])
    assert result.exit_code == 0
    assert "apex" in result.output
    assert "etsy" in result.output


def test_creds_list_json(tmp_path, monkeypatch):
    """List --json returns JSON without passwords."""
    monkeypatch.setenv("PEPPER_VAULT_PASSWORD", "testpass")
    vault_path = tmp_path / "credentials.kdbx"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)

    runner.invoke(
        app,
        ["creds", "set", "apex"],
        input="jeff@test.com\nsecret\n\n\n",
    )
    result = runner.invoke(app, ["creds", "list", "--json"])
    assert result.exit_code == 0
    assert "jeff@test.com" in result.output
    assert "secret" not in result.output


def test_creds_delete(tmp_path, monkeypatch):
    """Delete removes a credential."""
    monkeypatch.setenv("PEPPER_VAULT_PASSWORD", "testpass")
    vault_path = tmp_path / "credentials.kdbx"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)

    runner.invoke(
        app,
        ["creds", "set", "apex"],
        input="jeff@test.com\nsecret\n\n\n",
    )
    result = runner.invoke(app, ["creds", "delete", "apex"])
    assert result.exit_code == 0
    assert "Deleted" in result.output

    result = runner.invoke(app, ["creds", "get", "apex"])
    assert result.exit_code == 1


def test_creds_delete_not_found(tmp_path, monkeypatch):
    """Delete nonexistent service exits with code 1."""
    monkeypatch.setenv("PEPPER_VAULT_PASSWORD", "testpass")
    vault_path = tmp_path / "credentials.kdbx"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)

    result = runner.invoke(app, ["creds", "delete", "nonexistent"])
    assert result.exit_code == 1


def test_creds_init_creates_vault(tmp_path, monkeypatch):
    """Init creates the .kdbx file and writes password to .env."""
    monkeypatch.delenv("PEPPER_VAULT_PASSWORD", raising=False)
    vault_path = tmp_path / "credentials.kdbx"
    env_file = tmp_path / ".env"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)
    monkeypatch.setattr("pepper.credentials.cli._env_path", env_file)

    result = runner.invoke(
        app,
        ["creds", "init"],
        input="mypassword\nmypassword\n",
    )
    assert result.exit_code == 0
    assert "Created" in result.output
    assert vault_path.exists()
    assert "PEPPER_VAULT_PASSWORD=" in env_file.read_text()


def test_creds_init_already_exists(tmp_path, monkeypatch):
    """Init refuses to overwrite an existing vault."""
    vault_path = tmp_path / "credentials.kdbx"
    vault_path.touch()
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)

    result = runner.invoke(app, ["creds", "init"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_creds_init_password_mismatch(tmp_path, monkeypatch):
    """Init rejects mismatched passwords."""
    vault_path = tmp_path / "credentials.kdbx"
    env_file = tmp_path / ".env"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)
    monkeypatch.setattr("pepper.credentials.cli._env_path", env_file)

    result = runner.invoke(
        app,
        ["creds", "init"],
        input="password1\npassword2\n",
    )
    assert result.exit_code == 1
    assert "match" in result.output.lower()


def test_creds_no_password_env(tmp_path, monkeypatch):
    """Commands fail gracefully when PEPPER_VAULT_PASSWORD is not set."""
    monkeypatch.delenv("PEPPER_VAULT_PASSWORD", raising=False)
    vault_path = tmp_path / "credentials.kdbx"
    monkeypatch.setattr("pepper.credentials.cli._vault_path", vault_path)

    result = runner.invoke(app, ["creds", "list"])
    assert result.exit_code == 1
    assert "PEPPER_VAULT_PASSWORD" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_credential_cli.py -v`
Expected: FAIL — import errors

- [ ] **Step 3: Implement the CLI**

Create `src/pepper/credentials/cli.py`:

```python
"""Pepper creds CLI — manage stored credentials."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pykeepass import create_database
from rich import print as rprint

from pepper.credentials.store import CredentialStore

creds_app = typer.Typer(
    name="creds",
    help="Manage stored credentials.",
    no_args_is_help=True,
)

# Default paths — overridden in tests via monkeypatch
_vault_path = Path.home() / ".pepper" / "credentials.kdbx"
_env_path = Path.home() / ".pepper" / ".env"


def _store() -> CredentialStore:
    """Create a CredentialStore for the current vault path."""
    return CredentialStore(_vault_path)


@creds_app.command("init")
def init_vault() -> None:
    """Initialize the credential vault with a master password."""
    if _vault_path.exists():
        rprint(f"[red]Credential vault already exists at {_vault_path}[/red]")
        raise typer.Exit(1)

    password = typer.prompt("Master password", hide_input=True)
    confirm = typer.prompt("Confirm password", hide_input=True)

    if password != confirm:
        rprint("[red]Passwords do not match.[/red]")
        raise typer.Exit(1)

    _vault_path.parent.mkdir(parents=True, exist_ok=True)
    create_database(str(_vault_path), password=password)

    # Append to .env so Pepper and future CLI calls can unlock the vault
    with open(_env_path, "a", encoding="utf-8") as f:
        f.write(f"\nPEPPER_VAULT_PASSWORD={password}\n")

    rprint(f"[green]Created credential vault at {_vault_path} ✓[/green]")


@creds_app.command("set")
def set_credential(
    service: str = typer.Argument(help="Service name (e.g. apex, etsy)"),
) -> None:
    """Store a credential with secure password input."""
    username = typer.prompt("Username")
    password = typer.prompt("Password", hide_input=True)
    url = typer.prompt("URL (optional)", default="")
    notes = typer.prompt("Notes (optional)", default="")

    try:
        _store().set(service, username, password, url, notes)
    except ValueError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    rprint(f"[green]Saved {service} ✓[/green]")


@creds_app.command("get")
def get_credential(
    service: str = typer.Argument(help="Service name to retrieve"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON with password"),
) -> None:
    """Retrieve a stored credential."""
    try:
        cred = _store().get(service)
    except ValueError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    if cred is None:
        rprint(f"[red]No credential found for {service}[/red]")
        raise typer.Exit(1)

    if as_json:
        print(
            json.dumps(
                {
                    "service": cred.service,
                    "username": cred.username,
                    "password": cred.password,
                    "url": cred.url,
                    "notes": cred.notes,
                }
            )
        )
    else:
        rprint(f"[bold]Service:[/bold]  {cred.service}")
        rprint(f"[bold]Username:[/bold] {cred.username}")
        if cred.url:
            rprint(f"[bold]URL:[/bold]      {cred.url}")
        if cred.notes:
            rprint(f"[bold]Notes:[/bold]    {cred.notes}")


@creds_app.command("list")
def list_credentials(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List all stored credentials."""
    try:
        summaries = _store().list()
    except ValueError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    if as_json:
        print(
            json.dumps(
                [
                    {"service": s.service, "username": s.username, "url": s.url}
                    for s in summaries
                ]
            )
        )
    else:
        if not summaries:
            rprint("[yellow]No credentials stored.[/yellow]")
            return
        for s in summaries:
            rprint(s.service)


@creds_app.command("delete")
def delete_credential(
    service: str = typer.Argument(help="Service name to delete"),
) -> None:
    """Delete a stored credential."""
    try:
        deleted = _store().delete(service)
    except ValueError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1) from None

    if not deleted:
        rprint(f"[red]No credential found for {service}[/red]")
        raise typer.Exit(1)

    rprint(f"[green]Deleted {service} ✓[/green]")
```

- [ ] **Step 4: Register the subcommand on the main CLI**

In `src/pepper/cli.py`, add the import and registration after the existing `app` definition (after line 24):

```python
from pepper.credentials.cli import creds_app

app.add_typer(creds_app, name="creds", help="Manage stored credentials.")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_credential_cli.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run all unit tests for regression**

Run: `uv run pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add src/pepper/credentials/cli.py src/pepper/cli.py tests/unit/test_credential_cli.py
git commit -m "feat(creds): add pepper creds CLI subcommands"
```

---

### Task 5: Skill doc

**Files:**
- Create: `src/pepper/skills/creds/SKILL.md`

- [ ] **Step 1: Create the skill directory and doc**

Create `src/pepper/skills/creds/SKILL.md`:

```markdown
---
name: creds
description: Retrieve stored credentials for external services. Use when a playbook or task requires authentication — login to a website, API key, service credentials.
---

# Credentials

Jeff stores credentials securely via the `pepper creds` CLI. You retrieve them at runtime.

## Retrieving credentials

```bash
pepper creds get <service> --json
```

Returns JSON:
```json
{"service": "apex", "username": "jeff@example.com", "password": "...", "url": "https://apex.com", "notes": ""}
```

## Listing available credentials

```bash
pepper creds list --json
```

Returns a JSON array of services with usernames and URLs (no passwords).

## Rules

- **NEVER** echo, print, or include passwords in conversation text
- **NEVER** write passwords to files, vault, transcripts, or Discord
- Pass credentials directly to the tool that needs them (browser login, API call)
- If a credential is missing, tell Jeff: "I need credentials for X — please run `pepper creds set X`"
- You cannot create, update, or delete credentials — that's Jeff's interface
```

- [ ] **Step 2: Verify skill will be installed by `pepper init`**

The existing `_install_skills` in `generator.py` copies everything under `src/pepper/skills/` to the runtime. No code change needed — just verify:

Run: `ls src/pepper/skills/creds/SKILL.md`
Expected: file exists

- [ ] **Step 3: Commit**

```bash
git add src/pepper/skills/creds/SKILL.md
git commit -m "feat(creds): add skill doc for Pepper"
```

---

### Task 6: Playbook convention doc

**Files:**
- Create: `src/pepper/init/templates/playbook-README.md` (template copied to vault on init)
- Modify: `src/pepper/init/generator.py` (create playbooks dir + README)

- [ ] **Step 1: Write the playbook README template**

Create `src/pepper/init/templates/playbook-README.md`:

```markdown
# Playbooks

Playbooks are step-by-step instructions for multi-step workflows. Pepper reads
and follows them. They're just markdown files.

## Structure

Each playbook should include:
1. **Goal** — what this playbook accomplishes
2. **Steps** — numbered actions Pepper should take
3. **Credentials** — reference by service name: `pepper creds get <service> --json`
4. **Output** — where to send results (Discord channel, vault file, etc.)

## Example

```markdown
# Apex Screening Prep

**Goal:** Prepare a briefing before each candidate screening.

1. Run `pepper creds get apex --json` to retrieve login credentials
2. Open browser to the URL from the credential
3. Log in with the username and password
4. Pull today's candidate list
5. For each candidate, create a briefing in Memory/meetings/
6. Send summary embed to #pepper-chat
```

## Tips

- Be specific — Pepper has no prior context when following a playbook
- Reference exact tool names and Discord channels
- Use `pepper creds get <service> --json` for any credentials needed
- Playbooks can be wired to scheduler jobs for automation
```

- [ ] **Step 2: Add playbooks dir to vault scaffold**

In `src/pepper/init/generator.py`, add `"playbooks"` to `VAULT_SCAFFOLD_DIRS`:

```python
VAULT_SCAFFOLD_DIRS = [
    "daily/raw",
    "daily/summaries",
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
    "projects",
    "meetings",
    "research",
    "clients",
    "content",
    "team",
    "drafts/active",
    "drafts/sent",
    "tasks",
    "playbooks",
]
```

- [ ] **Step 3: Copy playbook README during init**

In `src/pepper/init/generator.py`, add after the Tier 1 files block (after the `for filename, default_content` loop, before `_install_skills`):

```python
    # Playbook README (only if not already present)
    playbook_readme = vault / "playbooks" / "README.md"
    if not playbook_readme.exists():
        readme_template = (
            Path(__file__).parent / "templates" / "playbook-README.md"
        )
        if readme_template.exists():
            playbook_readme.write_text(
                readme_template.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
```

- [ ] **Step 4: Run init test to verify no regression**

Run: `uv run pytest tests/unit/test_init.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/pepper/init/templates/playbook-README.md src/pepper/init/generator.py
git commit -m "feat(creds): add playbook convention with vault scaffold"
```

---

### Task 7: Final integration test

**Files:**
- No new files — run existing tests and manual verification

- [ ] **Step 1: Run full unit test suite**

Run: `uv run pytest tests/unit/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run type checker**

Run: `uv run mypy src/pepper/credentials/`
Expected: PASS (or known issues only)

- [ ] **Step 3: Run linter**

Run: `uv run ruff check src/pepper/credentials/`
Expected: PASS

- [ ] **Step 4: Manual smoke test of the full CLI flow**

```bash
export PEPPER_VAULT_PASSWORD=testmaster
pepper creds set testservice
# Enter: testuser / testpass / https://test.com / test notes
pepper creds get testservice
pepper creds get testservice --json
pepper creds list
pepper creds list --json
pepper creds delete testservice
pepper creds list
```

- [ ] **Step 5: Run `just gate` (full pre-merge check)**

Run: `just gate`
Expected: ALL PASS

- [ ] **Step 6: Final commit if any fixups needed, then ready for PR**

```bash
git add -A
git commit -m "fix: address any gate issues"
```
