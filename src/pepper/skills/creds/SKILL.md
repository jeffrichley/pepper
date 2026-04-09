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
