# Credential Store — Design Spec

**Date:** 2026-04-09
**Status:** Draft

## Problem

Pepper needs to authenticate to external services (Apex, Ed Discussion, Etsy, etc.) on Jeff's behalf. Currently there's no way to store credentials securely. Passwords typed in chat would land in transcripts and conversation history.

## Design

A `pepper creds` CLI subcommand backed by a pykeepass-encrypted `.kdbx` vault. Jeff uses the CLI with secure hidden input to store credentials. Pepper reads them programmatically in playbooks and ad-hoc tasks via Bash.

No MCP server. Same pattern as `gog` — just a CLI tool Pepper calls.

## Architecture

```
~/.pepper/credentials.kdbx        <- AES-256 encrypted (pykeepass)
~/.pepper/.env                     <- PEPPER_VAULT_PASSWORD (unlocks the kdbx)
src/pepper/credentials/            <- CLI implementation
~/.pepper/.claude/skills/creds/    <- Skill doc so Pepper knows how to use it
Memory/playbooks/                  <- Playbooks reference credentials by service name
```

## CLI Interface

All commands live under `pepper creds`, added as a Typer subcommand group on the existing `pepper` CLI.

### `pepper creds init`

First-time setup — creates the encrypted vault and writes the master password to `.env`.

```
$ pepper creds init
Master password: ••••••••
Confirm password: ••••••••
Created credential vault at ~/.pepper/credentials.kdbx ✓
```

- Uses hidden input for both password prompts
- Creates `~/.pepper/credentials.kdbx` with the given master password
- Appends `PEPPER_VAULT_PASSWORD=...` to `~/.pepper/.env`
- Refuses to run if `.kdbx` already exists (exits with code 1)
- After this, all other `pepper creds` commands just work

### `pepper creds set <service>`

Interactive — prompts for fields with hidden password input.

```
$ pepper creds set apex
Username: jeff@example.com
Password: ••••••••
URL (optional): https://apex.screening.com
Notes (optional): Apex screening platform
Saved apex ✓
```

- Uses `getpass.getpass()` for password (never echoed)
- Creates the `.kdbx` file on first use if it doesn't exist
- Overwrites existing entry for the same service name
- Fields: username (required), password (required), url (optional), notes (optional)

### `pepper creds get <service>`

Returns credential fields. Two modes:

```
# Human-readable (default) — password masked
$ pepper creds get apex
Service:  apex
Username: jeff@example.com
URL:      https://apex.screening.com

# Machine-readable — Pepper uses this
$ pepper creds get apex --json
{"service": "apex", "username": "jeff@example.com", "password": "hunter2", "url": "https://apex.screening.com", "notes": "Apex screening platform"}
```

- Default mode masks the password (for Jeff in terminal)
- `--json` includes the password (for Pepper via Bash tool)
- Exits with code 1 and error message if service not found

### `pepper creds list`

```
$ pepper creds list
apex
ed-discussion
etsy

$ pepper creds list --json
[{"service": "apex", "username": "jeff@example.com", "url": "https://apex.screening.com"}, ...]
```

- Never includes passwords in list output
- `--json` includes username and url for context, still no passwords

### `pepper creds delete <service>`

```
$ pepper creds delete apex
Deleted apex ✓
```

- Exits with code 1 if service not found
- No confirmation prompt (service name is explicit enough)

## Storage

### KeePass vault (`credentials.kdbx`)

- Created automatically on first `pepper creds set`
- Located at `~/.pepper/credentials.kdbx`
- Encrypted with AES-256 via pykeepass
- Master password from `PEPPER_VAULT_PASSWORD` environment variable
- Each credential is a KeePass entry in the root group:
  - Title = service name
  - UserName = username
  - Password = password
  - URL = url
  - Notes = notes

### Master password

- Stored in `~/.pepper/.env` as `PEPPER_VAULT_PASSWORD=...`
- Loaded into process environment by `_load_env()` in `cli.py` (already exists for Pepper startup)
- For the CLI commands, loaded by the `pepper creds` subcommand directly
- If not set, `pepper creds` commands print an error and exit

### Backup

- `credentials.kdbx` is inside `~/.pepper/`, so it's included in the existing vault backup to Google Drive automatically
- The backup is encrypted (tar.gz of already-encrypted file)

## Implementation

### Source layout

```
src/pepper/credentials/
├── __init__.py          # Public API: get_credential, set_credential, list_credentials, delete_credential
├── store.py             # pykeepass wrapper — open/close vault, CRUD operations
└── cli.py               # Typer subcommand group, registered on main app
```

### Dependencies

- `pykeepass` — KeePass .kdbx read/write
- Already have: `typer`, `rich` (for CLI output)

### Registration

In `src/pepper/cli.py`:

```python
from pepper.credentials.cli import creds_app

app.add_typer(creds_app, name="creds", help="Manage stored credentials.")
```

### Public API (`__init__.py`)

```python
def get_credential(service: str) -> Credential | None: ...
def set_credential(service: str, username: str, password: str, url: str = "", notes: str = "") -> None: ...
def list_credentials() -> list[CredentialSummary]: ...
def delete_credential(service: str) -> bool: ...
```

These are pure Python functions that open the vault, do the operation, and close it. Used by the CLI. Could also be imported directly if ever needed elsewhere.

### Models

```python
@dataclass
class Credential:
    service: str
    username: str
    password: str
    url: str
    notes: str

@dataclass
class CredentialSummary:
    service: str
    username: str
    url: str
```

## Skill Doc

Installed at `~/.pepper/.claude/skills/creds/SKILL.md` by `pepper init`. Tells Pepper:

- How to retrieve credentials: `pepper creds get <service> --json`
- That she should never log, print, or include passwords in conversation
- That she should pass credentials directly to the tool that needs them (browser, API call)
- List available credentials: `pepper creds list --json`
- She cannot create or delete credentials — that's Jeff's interface

## Playbook Convention

Playbooks reference credentials by service name:

```markdown
# Apex Screening Prep

1. Run `pepper creds get apex --json` to retrieve login credentials
2. Open browser to the URL from the credential
3. Log in with the username and password
4. Pull today's candidate list
5. For each candidate, create a briefing in Memory/meetings/
6. Send summary embed to #pepper-chat
```

Playbooks live in `Memory/playbooks/`. Pepper can create and edit them. They're just markdown with instructions.

## Security

- Passwords encrypted at rest (AES-256 in .kdbx)
- Master password in `.env` (already a protected path — Pepper can't read the file)
- `pepper creds get` default mode masks passwords (human use)
- `--json` mode exposes passwords (Pepper use via Bash) — this is intentional; she needs them to authenticate
- Pepper's skill doc instructs her to never echo credentials in conversation
- Credentials never appear in transcripts (Bash tool output is not transcribed by the pipeline)
- The `.kdbx` file is backed up encrypted to Google Drive

## What This Enables

With credential store + browser + scheduler, Pepper can self-serve all of these:

| Workflow | How |
|----------|-----|
| Apex screening prep | Playbook: creds + browser + calendar + vault |
| Ed Discussion monitoring | Playbook: creds + browser + scheduler |
| Etsy listing pipeline | Playbook: creds + browser + vault |
| Email triage | Already has gog (Gmail), no creds needed |
| Meeting prep/follow-up | Already has calendar + vault + scheduler |
| Project nudges | Already has vault + scheduler + Discord |
| Smart reminders | Already has vault + scheduler + Discord + calendar |
| Weekly activity reports | Already has /war skill |

## Out of Scope

- OAuth token management (gog handles that separately)
- Multi-user / shared vaults
- 2FA/TOTP automation (future consideration)
- Credential rotation / expiry tracking
