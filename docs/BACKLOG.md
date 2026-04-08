# Pepper Development Backlog

## Discord Integration

### High Priority — Core Capabilities
_Parity with official plugin + foundational features_

- [ ] Access control — DM policy (pairing/allowlist/disabled), per-channel guild opt-in, allowFrom lists. Prevents strangers from talking to Pepper.
- [ ] Edit message — `edit_message` tool for interim progress updates ("working..." -> result). Edits don't push-notify.
- [ ] Fetch message history — `fetch_messages` tool, oldest-first, up to 100 per call. Only lookback available (Discord search API not exposed to bots).
- [ ] Mention detection — respond to @mentions and reply-to-bot in guild channels. Ignore messages that don't address Pepper.
- [ ] Graceful shutdown — detect stdin EOF / SIGTERM, clean up Discord client before exit.
- [ ] Interactive briefing dashboard — morning briefing embed with buttons: [Tasks] [Calendar] [Priorities] [Projects]. Jeff taps a button, Pepper responds with that section expanded.
- [ ] Slash commands — register `/brief`, `/tasks`, `/focus`, `/status <project>` as real Discord slash commands with autocomplete for project names.
- [ ] Progress embeds with edit — send "Working on it..." embed, edit in-place as work progresses, final edit shows result. No message spam.

### Medium Priority — Power Features

- [ ] Thread/reply-to support — native Discord threading via `reply_to` param. Quote-reply to specific messages. Keep conversations organized.
- [ ] Smart chunking — paragraph-aware message splitting (prefer `\n\n` boundaries over hard 2000 char cut). Configurable chunkMode and textChunkLimit.
- [ ] Thread-based project discussions — when Jeff discusses a specific project, Pepper creates a thread for it. Main channel stays clean, project context stays together.
- [ ] Polls for decision making — when Jeff is scattered between projects, Pepper creates a poll: "What should we focus on?" with top options. Jeff votes, Pepper locks in.
- [ ] Permission relay — relay Claude Code permission prompts (allow/deny tool calls) to Discord DMs with interactive buttons.
- [ ] Attachment security — validate file paths before sending (refuse to send state files), size limits (25MB per file, 10 files max).
- [ ] Download attachments on demand — `download_attachment` tool for files sent in Discord messages.
- [ ] Scheduled events for deadlines — Pepper creates Discord scheduled events for upcoming deadlines. Native Discord notifications.

### Lower Priority — Pepper Superpowers

- [ ] Forum channel for ideas — turn #ideas into a Forum channel. Each idea gets its own thread with tags (business, tech, personal). Pepper auto-tags and summarizes.
- [ ] Modal forms for quick capture — button pops a modal: "Quick Capture" with fields for Title, Project, Priority. Pepper files directly into the vault.
- [ ] Voice channel alerts — Pepper joins a voice channel briefly to play a TTS alert for urgent items. Then leaves.
- [ ] Webhook personas — Pepper sends messages with different webhook avatars for different contexts (briefings, alerts, casual). Visual distinction.
- [ ] Role-based access — different Discord roles get different Pepper capabilities. Jeff gets full access, collaborators get limited.
- [ ] AutoMod integration — Pepper manages server AutoMod rules. If spam appears, she tightens rules and notifies Jeff.
- [ ] Configurable ack reaction — emoji react on receipt (configurable, can disable)
- [ ] Reply-to mode — configurable: first chunk only, all chunks, or off
- [ ] Outbound gate — only allow reply/fetch to channels in the access list
- [ ] Components V2 layouts — use LayoutView for rich dashboard-style messages with sections, media galleries, thumbnails alongside text

## Quality & Standards

- [ ] MyPy strict — 128+ type annotation errors across discord integration, channel server, and skills
- [ ] Coverage 80% — currently at 50%, runtime infrastructure needs tests
- [ ] drill-sergeant AAA — add Arrange/Act/Assert structure to all tests (standard says off, but good practice)

## Attachment System

- [ ] Discord attachment download, storage, cleanup (spec at docs/superpowers/specs/2026-04-07-discord-attachments-design.md)
