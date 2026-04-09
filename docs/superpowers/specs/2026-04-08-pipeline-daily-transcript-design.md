# Pipeline & Daily Transcript Design

**Goal:** Replace the broken agent-driven daily logging with an automatic transcript capture system built on a message pipeline in the channel server.

**Architecture:** A `pepper/pipeline/` package defines a hook-based transform pipeline. The channel server calls it at two points (inbound message, outbound reply). The first hook is a transcript writer that appends JSONL to `~/.pepper/Memory/daily/raw/YYYY-MM-DD.jsonl`. Old session hooks are removed entirely.

---

## 1. Data Model

### PipelineMessage

Pydantic model in `pepper/pipeline/model.py`:

```python
class PipelineMessage(BaseModel):
    direction: Literal["inbound", "outbound"]
    timestamp: str          # ISO 8601
    source: str             # "discord", "scheduler", "cli", etc.
    chat_id: str            # existing chat_id from channel server
    sender: str             # display name
    content: str            # message text
    metadata: dict[str, str]  # pass-through from channel server
```

### Hook type

```python
Hook = Callable[[PipelineMessage], PipelineMessage | None]
```

A hook receives a message, returns it (possibly modified) to continue the chain, or returns `None` to drop the message from the pipeline. Dropping from the pipeline means the message is not delivered — use with care.

### JSONL line format

Each line in the daily transcript file is a `PipelineMessage` serialized with short keys:

```json
{"ts": "2026-04-08T18:22:03", "dir": "inbound", "src": "discord", "cid": "discord-999-123-456", "sender": "Jeff", "content": "is there anything getting written to our daily logs yet?"}
```

Fields: `ts`, `dir`, `src`, `cid` (chat_id), `sender`, `content`. No metadata blob — keep lines compact.

---

## 2. Package Structure

```
pepper/
├── pipeline/
│   ├── __init__.py          # exports run_inbound(), run_outbound()
│   ├── model.py             # PipelineMessage
│   ├── runner.py            # run_hooks(hooks, message) -> message | None
│   └── hooks/
│       ├── __init__.py      # INBOUND_HOOKS and OUTBOUND_HOOKS lists
│       └── transcript.py    # JSONL daily log writer
```

---

## 3. Pipeline Runner

`pipeline/runner.py`:

```python
def run_hooks(hooks: list[Hook], message: PipelineMessage) -> PipelineMessage | None:
    for hook in hooks:
        message = hook(message)
        if message is None:
            return None
    return message
```

`pipeline/__init__.py` exports two convenience functions:

```python
def run_inbound(message: PipelineMessage) -> PipelineMessage | None:
    return run_hooks(INBOUND_HOOKS, message)

def run_outbound(message: PipelineMessage) -> PipelineMessage | None:
    return run_hooks(OUTBOUND_HOOKS, message)
```

---

## 4. Transcript Hook

`pipeline/hooks/transcript.py`:

- Appends one JSON line per message to `~/.pepper/Memory/daily/raw/YYYY-MM-DD.jsonl`
- Uses `filelock` for concurrency safety (same pattern as existing vault I/O)
- Uses `get_vault_path()` from `hooks/shared.py` for vault resolution
- Returns the message unchanged (pure observer)
- On write failure: logs a warning, returns message unchanged. Never blocks delivery.

### Async integration

The channel server is async. The transcript hook's file write is blocking (filelock). The channel server must call it via `asyncio.to_thread()` or the runner must handle this. Since hooks are sync callables, the runner itself should be called from `asyncio.to_thread()` when invoked from async code:

```python
# In channel server
message = await asyncio.to_thread(run_inbound, pipeline_message)
```

This keeps hook implementations simple (no async required) while not blocking the event loop.

---

## 5. Channel Server Integration

Two integration points in `pepper/channel/server.py`:

### Inbound (POST /message handler, ~line 215)

After parsing the request body, before routing to Claude:

```python
pipeline_msg = PipelineMessage(
    direction="inbound",
    timestamp=datetime.now(UTC).isoformat(),
    source=data["source"],
    chat_id=data["chat_id"],
    sender=data.get("sender", "unknown"),
    content=data["content"],
    metadata={k: str(v) for k, v in data.get("metadata", {}).items()},
)
result = await asyncio.to_thread(run_inbound, pipeline_msg)
if result is None:
    # Hook dropped the message
    return web.json_response({"status": "dropped", "chat_id": chat_id})
```

### Outbound (reply tool handler, ~line 411)

After constructing the reply data, before emitting to SSE:

```python
pipeline_msg = PipelineMessage(
    direction="outbound",
    timestamp=datetime.now(UTC).isoformat(),
    source=source,
    chat_id=chat_id,
    sender="Pepper",
    content=text,
    metadata=metadata or {},
)
result = await asyncio.to_thread(run_outbound, pipeline_msg)
if result is None:
    return  # Hook dropped the reply
```

---

## 6. Removals

### Files to delete

- `src/pepper/hooks/session_start_context.py`
- `src/pepper/hooks/pre_compact_flush.py`
- `src/pepper/hooks/session_end_flush.py`

### Functions to remove from `hooks/shared.py`

- `append_to_daily_log()` — replaced by transcript hook
- `session_already_logged()` — no longer needed
- `read_stdin()` — only used by deleted hooks
- `write_stdout()` — only used by deleted hooks

### Functions to keep in `hooks/shared.py`

- `get_vault_path()` — used by transcript hook
- `get_daily_log_path()` — update to return `.jsonl` extension, used by transcript hook

### Functions to delete from `hooks/shared.py`

- `read_tier1_files()` — only caller was `session_start_context.py` (deleted). Pepper reads vault files directly via CLAUDE.md directive now.
- `read_recent_summaries()` — only caller was `session_start_context.py` (deleted). Pepper reads summaries directly via CLAUDE.md directive now.
- `TIER_1_FILES` constant — only used by `read_tier1_files()`

### Tests to delete

- `tests/integration/test_session_start.py`
- `tests/integration/test_session_end.py`
- `tests/integration/test_pre_compact.py`
- Remove `append_to_daily_log` and `session_already_logged` tests from `tests/unit/test_shared.py` (if any)
- Remove concurrent daily log write tests from `tests/integration/` (if any)

### Config to update

- `src/pepper/init/templates/settings.json.j2` — remove all three hook entries from the `hooks` section
- Runtime `~/.pepper/.claude/settings.json` — remove hook entries (done by user on next `pepper init` or manually)

---

## 7. Nightly Reflection Update

Update `src/pepper/scheduler/jobs.yaml` nightly_reflection prompt to reference JSONL:

```yaml
nightly_reflection:
  trigger: cron
  schedule:
    hour: 3
    minute: 0
  prompt: >
    Nightly reflection: Read today's transcript from Memory/daily/raw/YYYY-MM-DD.jsonl.
    Each line is a JSON object with fields: ts, dir, src, cid, sender, content.
    Summarize the day's conversations into Memory/daily/summaries/YYYY-MM-DD.md.
    Identify patterns, decisions made, and open loops.
    Send a brief summary to pepper-chat Discord channel.
  channel_hint: "#pepper-chat"
```

---

## 8. Runtime CLAUDE.md Update

Add a directive to Pepper's runtime CLAUDE.md (`~/.pepper/CLAUDE.md`) or the init template that generates it:

```markdown
## Session Context

At the start of every session, read these files from your vault (~/.pepper/Memory/):
- IDENTITY.md — who you are
- SOUL.md — how you think and behave
- USER.md — about Jeff
- MEMORY.md — persistent memory
- OPERATIONS.md — how you operate

Also read the most recent 2 daily summaries from Memory/daily/summaries/ for recent context.
```

This replaces the SessionStart hook's context injection.

---

## 9. Testing

### Unit tests

- `test_pipeline_model.py` — PipelineMessage creation, serialization
- `test_pipeline_runner.py` — run_hooks with pass-through, transform, and drop scenarios
- `test_transcript_hook.py` — writes JSONL, handles errors gracefully, filelock safety

### Integration tests

- `test_pipeline_integration.py` — full inbound/outbound flow through channel server with transcript verification
- `test_transcript_concurrent.py` — multiple threads writing simultaneously (mirrors existing concurrent test pattern)

---

## 10. What This Does NOT Cover

- Discord bot changes — no logging in `bot.py`, everything flows through the channel server
- Scheduler changes (beyond nightly reflection prompt update)
- Morning briefing job — reads summaries, unaffected
- Migration of old markdown daily logs — they stay as-is, nightly reflection just reads JSONL going forward
