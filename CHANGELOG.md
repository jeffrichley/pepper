# Changelog

All notable changes to Pepper are documented here.

## [0.1.0.0] - 2026-04-08

### Added
- **Discord access control** with DM policy (allowlist/disabled), per-channel guild opt-in, mention detection via @mention, reply-to-bot, and custom regex patterns
- **edit_message tool** for in-place message updates without push notifications
- **fetch_messages tool** returning oldest-first messages with attachment counts and is_bot flag (up to 100)
- **Graceful shutdown** on stdin EOF, SIGTERM, and SIGINT so the bot doesn't zombie after Claude Code exits
- **Paragraph-aware message chunking** that splits at natural boundaries instead of hard 2000-char cuts
- **reply_to parameter** on send_discord_message for native Discord quote-reply threading
- **Slash commands** /brief, /tasks, /focus, /status with access control and autocomplete
- **Interactive briefing dashboard** with button navigation (Tasks, Calendar, Priorities, Projects)
- **create_thread tool** for organizing project discussions into Discord threads
- **create_poll tool** using Discord's native poll feature for prioritization decisions
- **Scheduled events tools** (create, list, cancel) for deadline notifications via Discord events
- **Attachment security** with path validation, 25MB size limit, 10 file max, protected dir blocking
- **download_attachments tool** for on-demand file download from Discord messages
- **Configurable ack reaction** on message receipt
- **Outbound channel gate** helper for allowlist checking
- **Scheduler skill** with tool documentation and examples for interval and cron jobs
- **Roadmap** with mermaid dependency graph and batch execution plan

### Changed
- **Scheduler split** into independent MCP server (pepper-scheduler), separate from Discord
- **Attachments no longer auto-downloaded** on every message. Metadata (URL, filename, type, size) is passed instead. Use download_attachments tool when needed.
- **Attachment cleanup** moved from scheduler cron to Discord bot process (runs on startup + every 6 hours)
- **Version** now read from VERSION file (4-digit format) instead of hardcoded in pyproject.toml
- **Official Discord plugin disabled** globally. Custom pepper-discord handles everything.
- **MCP config** now includes three servers: pepper-channel, pepper-discord, pepper-scheduler
