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
