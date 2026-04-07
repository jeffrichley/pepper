# Discord Attachment Handling Design

**Date:** 2026-04-07
**Status:** Approved

## Problem

Pepper's Discord bot only forwards message text. File attachments (images, PDFs, documents) sent via Discord are silently dropped. Pepper also can't send files back through Discord.

## Solution

Download inbound attachments to local storage, pass local paths to Pepper via the channel message. Support outbound file attachments in replies. Daily cleanup job manages storage with age and size limits.

## Inbound (Discord -> Pepper)

When a Discord message has attachments, the bot:

1. Downloads each file from the Discord CDN to `~/.pepper/attachments/YYYY-MM-DD/<message_id>_<filename>`
2. Appends a short indicator to message content for each file: `[📎 filename.ext]`
3. Adds structured attachment info to the metadata dict:
```json
{
  "attachments": "[{\"filename\": \"report.pdf\", \"content_type\": \"application/pdf\", \"path\": \"/path/to/attachments/2026-04-07/abc123_report.pdf\", \"size_bytes\": 52400}]"
}
```
Metadata values are strings (channel server constraint), so the attachments list is JSON-encoded.

## Outbound (Pepper -> Discord)

The `reply` tool already accepts a `metadata` dict. Add support for an `attachments` field:
```json
{
  "chat_id": "discord-...",
  "text": "Here's the report",
  "metadata": {
    "attachments": ["/path/to/file.pdf"]
  }
}
```

The Discord bot's SSE reply handler reads the `attachments` list from metadata, loads each file, and sends them as Discord file attachments alongside the text message.

## Storage

- **Location:** `~/.pepper/attachments/`
- **Organization:** `YYYY-MM-DD/` subdirectories by date
- **Naming:** `<message_id>_<original_filename>` to avoid collisions
- **Outside the vault:** Won't be indexed by pyqmd or loaded by hooks

## Cleanup Job

Daily cron job at 4 AM (after the 3 AM reflection), added to `jobs.yaml`:

1. Delete all files older than 30 days
2. If total directory size exceeds 500MB, delete oldest files until under the cap

This is a direct Python function call, not a Claude prompt — pure housekeeping, no agent reasoning needed. Registered as a schedulable function in the scheduler module alongside `execute_job`.

## Files

- Create: `src/pepper/attachments.py` — download helper, cleanup logic, storage path management
- Modify: `src/pepper/integrations/discord/bot.py` — download attachments in `on_message`, send file attachments in `handle_reply`
- Modify: `src/pepper/integrations/discord/jobs.yaml` — add `attachment_cleanup` job
- Modify: `src/pepper/integrations/discord/scheduler.py` — register cleanup as a schedulable function
- Test: `tests/test_attachments.py` — download, path management, cleanup logic
