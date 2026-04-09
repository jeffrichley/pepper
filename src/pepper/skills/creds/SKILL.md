---
name: creds
description: Retrieve stored credentials for external services. Use when a playbook or task requires authentication — logging into a website, API keys, service credentials. Also use when Jeff asks you to check what credentials are available or when a workflow fails due to missing authentication.
---

# Credentials

Jeff stores credentials securely in an encrypted KeePass vault via the `pepper creds` CLI. You retrieve them at runtime via Bash. Credentials are encrypted at rest (AES-256) and unlocked automatically from the environment.

## Quick Reference

| Action | Command |
|--------|---------|
| Get a credential (with password) | `pepper creds get <service> --json` |
| List all credentials | `pepper creds list --json` |
| Check if a credential exists | `pepper creds list --json` and check the output |

## Retrieving Credentials

```bash
pepper creds get apex --json
```

Returns:
```json
{"service": "apex", "username": "jeff@example.com", "password": "s3cret", "url": "https://apex.example.com", "notes": "Apex screening platform"}
```

**Fields:**
- `service` — the identifier Jeff used when storing it
- `username` — login username or email
- `password` — the secret (only included with `--json`)
- `url` — the service URL (may be empty)
- `notes` — Jeff's notes about the service (may be empty)

## Listing Available Credentials

```bash
pepper creds list --json
```

Returns a JSON array with service names, usernames, and URLs. **Never includes passwords.** Use this to check what's available before attempting a workflow.

```json
[{"service": "apex", "username": "jeff@example.com", "url": "https://apex.example.com"}, ...]
```

## Using Credentials with the Browser

This is the most common pattern — logging into a website on Jeff's behalf.

**Step-by-step:**
1. Retrieve the credential: `pepper creds get <service> --json`
2. Parse the JSON to extract username, password, and URL
3. Navigate to the URL in the browser
4. Find the login form fields and enter the username and password
5. Submit the form
6. Verify you're logged in before proceeding

**Example in a playbook:**
```
1. Run `pepper creds get apex --json` to get login credentials
2. Browse to the URL from the credential
3. Enter the username in the email/username field
4. Enter the password in the password field
5. Click the login/sign-in button
6. Wait for the dashboard to load — verify login succeeded
7. Proceed with the task...
```

## Using Credentials with APIs

For services with API keys or tokens stored as credentials:

1. Retrieve the credential: `pepper creds get <service> --json`
2. Use the password field as the API key/token in your request
3. The notes field may contain additional context (base URL, API version, etc.)

## Playbook Pattern

Playbooks live in `Memory/playbooks/` and reference credentials by service name. When following a playbook that mentions credentials, use the exact service name specified.

A well-structured playbook looks like:
```markdown
# Workflow Name

**Goal:** What this accomplishes

1. Run `pepper creds get <service> --json` to retrieve login credentials
2. [Browser/API steps using those credentials]
3. [Task-specific actions]
4. [Where to send results — Discord channel, vault file, etc.]
```

## When Credentials Are Missing

If you try to retrieve a credential and it doesn't exist:
- **Don't guess or skip the step**
- Tell Jeff clearly: "I need credentials for X — please run `pepper creds set X`"
- Explain what the credential is for so Jeff knows what username/password to store
- Wait for Jeff to confirm before retrying

## Security Rules

These are **hard rules** — never break them:

- **NEVER** echo, print, repeat, or include passwords in conversation text, Discord messages, or any visible output
- **NEVER** write passwords to files, vault, transcripts, daily logs, or Memory/
- **NEVER** include passwords in tool call arguments that get logged (e.g., don't put a password in a Discord message)
- **DO** pass credentials directly from the Bash tool result to the action that needs them (browser form fill, API header)
- **DO** treat the entire `--json` output as sensitive — don't quote it back to Jeff
- If Jeff asks "what's my password for X" — tell him to run `pepper creds get X` himself, don't retrieve and display it

## What You Cannot Do

- You cannot create, update, or delete credentials — that's Jeff's interface via the terminal
- You cannot change the master password
- You cannot access the raw `.kdbx` file — always use the CLI

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `PEPPER_VAULT_PASSWORD not set` | Environment not loaded | This should not happen during normal Pepper operation — the env is loaded at startup. Ask Jeff to restart Pepper. |
| `No credential found for X` | Jeff hasn't stored it yet | Ask Jeff to run `pepper creds set X` |
| Login fails with correct credentials | Password may have changed | Tell Jeff the login failed and ask him to update with `pepper creds set X` (overwrites the old entry) |
