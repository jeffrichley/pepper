# Pipeline & Daily Transcript Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broken agent-driven daily logging with an automatic transcript capture system built on a message pipeline in the channel server.

**Architecture:** A `pepper/pipeline/` package defines a hook-based transform pipeline. The channel server calls `run_inbound()` / `run_outbound()` at two interception points. A transcript hook appends JSONL to `~/.pepper/Memory/daily/raw/YYYY-MM-DD.jsonl`. Old session hooks are deleted.

**Tech Stack:** Python 3.12, Pydantic, filelock, asyncio, pytest

---

## File Structure

| File | Responsibility |
|------|---------------|
| **Create:** `src/pepper/pipeline/__init__.py` | Exports `run_inbound()`, `run_outbound()` |
| **Create:** `src/pepper/pipeline/model.py` | `PipelineMessage` Pydantic model |
| **Create:** `src/pepper/pipeline/runner.py` | `run_hooks()` — runs hook chain in sequence |
| **Create:** `src/pepper/pipeline/hooks/__init__.py` | `INBOUND_HOOKS` and `OUTBOUND_HOOKS` lists |
| **Create:** `src/pepper/pipeline/hooks/transcript.py` | JSONL daily log writer |
| **Create:** `tests/unit/test_pipeline_model.py` | PipelineMessage tests |
| **Create:** `tests/unit/test_pipeline_runner.py` | Hook runner tests |
| **Create:** `tests/unit/test_transcript_hook.py` | Transcript hook tests |
| **Modify:** `src/pepper/channel/server.py:208-248,397-420` | Wire pipeline into inbound/outbound |
| **Modify:** `src/pepper/hooks/shared.py` | Strip to `get_vault_path()` + `get_daily_log_path()` |
| **Modify:** `src/pepper/scheduler/jobs.yaml:24-34` | Update nightly reflection prompt for JSONL |
| **Modify:** `src/pepper/init/templates/settings.json.j2` | Remove hook entries |
| **Modify:** `src/pepper/init/templates/CLAUDE.md.j2` | Replace hook references with vault read directive |
| **Modify:** `tests/conftest.py` | Remove `mock_stdin_data` and `temp_transcript` fixtures |
| **Delete:** `src/pepper/hooks/session_start_context.py` | Old SessionStart hook |
| **Delete:** `src/pepper/hooks/pre_compact_flush.py` | Old PreCompact hook |
| **Delete:** `src/pepper/hooks/session_end_flush.py` | Old SessionEnd hook |
| **Delete:** `tests/integration/test_session_start.py` | Tests for deleted hook |
| **Delete:** `tests/integration/test_session_end.py` | Tests for deleted hook |
| **Delete:** `tests/integration/test_pre_compact.py` | Tests for deleted hook |

---

### Task 1: PipelineMessage Model

**Files:**
- Create: `src/pepper/pipeline/__init__.py`
- Create: `src/pepper/pipeline/model.py`
- Test: `tests/unit/test_pipeline_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_pipeline_model.py
"""Tests for PipelineMessage model."""

import json

import pytest


@pytest.mark.unit
def test_pipeline_message_creation():
    """PipelineMessage can be created with required fields."""
    from pepper.pipeline.model import PipelineMessage

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:22:03",
        source="discord",
        chat_id="discord-999-123-456",
        sender="Jeff",
        content="hello pepper",
        metadata={"channel_id": "123"},
    )
    assert msg.direction == "inbound"
    assert msg.source == "discord"
    assert msg.sender == "Jeff"
    assert msg.content == "hello pepper"


@pytest.mark.unit
def test_pipeline_message_to_transcript_json():
    """PipelineMessage serializes to compact JSONL format."""
    from pepper.pipeline.model import PipelineMessage

    msg = PipelineMessage(
        direction="outbound",
        timestamp="2026-04-08T18:22:15",
        source="discord",
        chat_id="discord-999-123-456",
        sender="Pepper",
        content="Hey Jeff!",
        metadata={},
    )
    line = msg.to_transcript_json()
    parsed = json.loads(line)
    assert parsed["ts"] == "2026-04-08T18:22:15"
    assert parsed["dir"] == "outbound"
    assert parsed["src"] == "discord"
    assert parsed["cid"] == "discord-999-123-456"
    assert parsed["sender"] == "Pepper"
    assert parsed["content"] == "Hey Jeff!"
    # No metadata key in transcript output
    assert "metadata" not in parsed


@pytest.mark.unit
def test_pipeline_message_default_metadata():
    """Metadata defaults to empty dict."""
    from pepper.pipeline.model import PipelineMessage

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:00:00",
        source="scheduler",
        chat_id="sched-1",
        sender="system",
        content="heartbeat",
    )
    assert msg.metadata == {}


@pytest.mark.unit
def test_pipeline_message_invalid_direction():
    """Invalid direction raises validation error."""
    from pydantic import ValidationError

    from pepper.pipeline.model import PipelineMessage

    with pytest.raises(ValidationError):
        PipelineMessage(
            direction="sideways",
            timestamp="2026-04-08T18:00:00",
            source="test",
            chat_id="test-1",
            sender="test",
            content="test",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_pipeline_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pepper.pipeline'`

- [ ] **Step 3: Create the pipeline package and model**

```python
# src/pepper/pipeline/__init__.py
"""Pepper message pipeline — hook-based transform chain for inbound/outbound messages."""
```

```python
# src/pepper/pipeline/model.py
"""Pipeline message model — the unit of data flowing through hooks."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field


class PipelineMessage(BaseModel):
    """A message flowing through the pipeline.

    Represents either an inbound message (from an integration to Claude)
    or an outbound reply (from Claude to an integration).
    """

    direction: Literal["inbound", "outbound"]
    timestamp: str
    source: str
    chat_id: str
    sender: str
    content: str
    metadata: dict[str, str] = Field(default_factory=dict)

    def to_transcript_json(self) -> str:
        """Serialize to compact JSON for JSONL transcript files."""
        return json.dumps(
            {
                "ts": self.timestamp,
                "dir": self.direction,
                "src": self.source,
                "cid": self.chat_id,
                "sender": self.sender,
                "content": self.content,
            },
            ensure_ascii=False,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_pipeline_model.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pepper/pipeline/__init__.py src/pepper/pipeline/model.py tests/unit/test_pipeline_model.py
git commit -m "feat: add PipelineMessage model for message pipeline"
```

---

### Task 2: Pipeline Runner

**Files:**
- Modify: `src/pepper/pipeline/__init__.py`
- Create: `src/pepper/pipeline/runner.py`
- Test: `tests/unit/test_pipeline_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_pipeline_runner.py
"""Tests for pipeline hook runner."""

import pytest


@pytest.mark.unit
def test_run_hooks_passthrough():
    """Hooks that return the message pass it through unchanged."""
    from pepper.pipeline.model import PipelineMessage
    from pepper.pipeline.runner import run_hooks

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:00:00",
        source="test",
        chat_id="test-1",
        sender="tester",
        content="hello",
    )

    def passthrough(m: PipelineMessage) -> PipelineMessage:
        return m

    result = run_hooks([passthrough], msg)
    assert result is not None
    assert result.content == "hello"


@pytest.mark.unit
def test_run_hooks_transform():
    """Hook can modify the message."""
    from pepper.pipeline.model import PipelineMessage
    from pepper.pipeline.runner import run_hooks

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:00:00",
        source="test",
        chat_id="test-1",
        sender="tester",
        content="hello",
    )

    def upper_hook(m: PipelineMessage) -> PipelineMessage:
        return m.model_copy(update={"content": m.content.upper()})

    result = run_hooks([upper_hook], msg)
    assert result is not None
    assert result.content == "HELLO"


@pytest.mark.unit
def test_run_hooks_drop():
    """Hook returning None drops the message."""
    from pepper.pipeline.model import PipelineMessage
    from pepper.pipeline.runner import run_hooks

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:00:00",
        source="test",
        chat_id="test-1",
        sender="tester",
        content="hello",
    )

    def drop_hook(m: PipelineMessage) -> None:
        return None

    result = run_hooks([drop_hook], msg)
    assert result is None


@pytest.mark.unit
def test_run_hooks_chain_order():
    """Hooks run in order, each receiving the previous hook's output."""
    from pepper.pipeline.model import PipelineMessage
    from pepper.pipeline.runner import run_hooks

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:00:00",
        source="test",
        chat_id="test-1",
        sender="tester",
        content="a",
    )

    def append_b(m: PipelineMessage) -> PipelineMessage:
        return m.model_copy(update={"content": m.content + "b"})

    def append_c(m: PipelineMessage) -> PipelineMessage:
        return m.model_copy(update={"content": m.content + "c"})

    result = run_hooks([append_b, append_c], msg)
    assert result is not None
    assert result.content == "abc"


@pytest.mark.unit
def test_run_hooks_drop_stops_chain():
    """After a hook drops, subsequent hooks don't run."""
    from pepper.pipeline.model import PipelineMessage
    from pepper.pipeline.runner import run_hooks

    called = []

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:00:00",
        source="test",
        chat_id="test-1",
        sender="tester",
        content="hello",
    )

    def drop_hook(m: PipelineMessage) -> None:
        called.append("drop")
        return None

    def after_hook(m: PipelineMessage) -> PipelineMessage:
        called.append("after")
        return m

    run_hooks([drop_hook, after_hook], msg)
    assert called == ["drop"]


@pytest.mark.unit
def test_run_hooks_empty_list():
    """Empty hook list passes message through."""
    from pepper.pipeline.model import PipelineMessage
    from pepper.pipeline.runner import run_hooks

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:00:00",
        source="test",
        chat_id="test-1",
        sender="tester",
        content="hello",
    )

    result = run_hooks([], msg)
    assert result is not None
    assert result.content == "hello"


@pytest.mark.unit
def test_run_inbound_and_outbound():
    """run_inbound and run_outbound are importable convenience functions."""
    from pepper.pipeline import run_inbound, run_outbound

    assert callable(run_inbound)
    assert callable(run_outbound)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_pipeline_runner.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_hooks' from 'pepper.pipeline.runner'`

- [ ] **Step 3: Implement the runner and hook registration**

```python
# src/pepper/pipeline/runner.py
"""Pipeline hook runner — executes hooks in sequence on a message."""

from __future__ import annotations

from collections.abc import Callable

from pepper.pipeline.model import PipelineMessage

Hook = Callable[[PipelineMessage], PipelineMessage | None]


def run_hooks(
    hooks: list[Hook],
    message: PipelineMessage,
) -> PipelineMessage | None:
    """Run hooks in sequence. Returns None if any hook drops the message."""
    for hook in hooks:
        result = hook(message)
        if result is None:
            return None
        message = result
    return message
```

```python
# src/pepper/pipeline/hooks/__init__.py
"""Pipeline hook registration — lists of hooks for inbound and outbound messages."""

from __future__ import annotations

from pepper.pipeline.runner import Hook

# Hooks are called in order. Each receives the message from the previous hook.
# Return None from a hook to drop the message.
INBOUND_HOOKS: list[Hook] = []
OUTBOUND_HOOKS: list[Hook] = []
```

Update `src/pepper/pipeline/__init__.py`:

```python
"""Pepper message pipeline — hook-based transform chain for inbound/outbound messages."""

from pepper.pipeline.hooks import INBOUND_HOOKS, OUTBOUND_HOOKS
from pepper.pipeline.runner import run_hooks


def run_inbound(message: "PipelineMessage") -> "PipelineMessage | None":
    """Run all inbound hooks on a message."""
    return run_hooks(INBOUND_HOOKS, message)


def run_outbound(message: "PipelineMessage") -> "PipelineMessage | None":
    """Run all outbound hooks on a message."""
    return run_hooks(OUTBOUND_HOOKS, message)
```

Note: Use `from __future__ import annotations` at the top so the string quotes on PipelineMessage aren't needed. The full file:

```python
# src/pepper/pipeline/__init__.py
"""Pepper message pipeline — hook-based transform chain for inbound/outbound messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pepper.pipeline.hooks import INBOUND_HOOKS, OUTBOUND_HOOKS
from pepper.pipeline.runner import run_hooks

if TYPE_CHECKING:
    from pepper.pipeline.model import PipelineMessage


def run_inbound(message: PipelineMessage) -> PipelineMessage | None:
    """Run all inbound hooks on a message."""
    return run_hooks(INBOUND_HOOKS, message)


def run_outbound(message: PipelineMessage) -> PipelineMessage | None:
    """Run all outbound hooks on a message."""
    return run_hooks(OUTBOUND_HOOKS, message)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_pipeline_runner.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/pepper/pipeline/ tests/unit/test_pipeline_runner.py
git commit -m "feat: add pipeline hook runner with inbound/outbound chains"
```

---

### Task 3: Transcript Hook

**Files:**
- Create: `src/pepper/pipeline/hooks/transcript.py`
- Modify: `src/pepper/pipeline/hooks/__init__.py`
- Test: `tests/unit/test_transcript_hook.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_transcript_hook.py
"""Tests for the transcript pipeline hook."""

import json
import threading

import pytest


@pytest.mark.unit
def test_transcript_hook_writes_jsonl(tmp_path, monkeypatch):
    """Transcript hook appends a JSONL line to the daily raw file."""
    monkeypatch.setenv("PEPPER_VAULT_PATH", str(tmp_path))

    from pepper.pipeline.hooks.transcript import transcript_hook
    from pepper.pipeline.model import PipelineMessage

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:22:03",
        source="discord",
        chat_id="discord-999-123-456",
        sender="Jeff",
        content="hello pepper",
    )

    result = transcript_hook(msg)

    # Hook returns message unchanged
    assert result is not None
    assert result.content == "hello pepper"

    # JSONL file was created
    raw_dir = tmp_path / "daily" / "raw"
    jsonl_files = list(raw_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 1

    lines = jsonl_files[0].read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1

    parsed = json.loads(lines[0])
    assert parsed["ts"] == "2026-04-08T18:22:03"
    assert parsed["dir"] == "inbound"
    assert parsed["src"] == "discord"
    assert parsed["cid"] == "discord-999-123-456"
    assert parsed["sender"] == "Jeff"
    assert parsed["content"] == "hello pepper"


@pytest.mark.unit
def test_transcript_hook_appends(tmp_path, monkeypatch):
    """Multiple messages append to the same file."""
    monkeypatch.setenv("PEPPER_VAULT_PATH", str(tmp_path))

    from pepper.pipeline.hooks.transcript import transcript_hook
    from pepper.pipeline.model import PipelineMessage

    msg1 = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:22:03",
        source="discord",
        chat_id="discord-999-123-456",
        sender="Jeff",
        content="first message",
    )
    msg2 = PipelineMessage(
        direction="outbound",
        timestamp="2026-04-08T18:22:15",
        source="discord",
        chat_id="discord-999-123-456",
        sender="Pepper",
        content="second message",
    )

    transcript_hook(msg1)
    transcript_hook(msg2)

    raw_dir = tmp_path / "daily" / "raw"
    jsonl_files = list(raw_dir.glob("*.jsonl"))
    lines = jsonl_files[0].read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["content"] == "first message"
    assert json.loads(lines[1])["content"] == "second message"


@pytest.mark.unit
def test_transcript_hook_survives_write_error(tmp_path, monkeypatch):
    """Hook returns the message even if file write fails."""
    # Point to a path that can't be written (file as directory)
    bad_path = tmp_path / "daily" / "raw"
    bad_path.mkdir(parents=True)
    # Create a file where the JSONL file would go, blocking the write
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    blocker = bad_path / f"{today}.jsonl"
    blocker.mkdir()  # directory instead of file — write will fail

    monkeypatch.setenv("PEPPER_VAULT_PATH", str(tmp_path))

    from pepper.pipeline.hooks.transcript import transcript_hook
    from pepper.pipeline.model import PipelineMessage

    msg = PipelineMessage(
        direction="inbound",
        timestamp="2026-04-08T18:22:03",
        source="discord",
        chat_id="test-1",
        sender="Jeff",
        content="this should not crash",
    )

    # Should not raise
    result = transcript_hook(msg)
    assert result is not None
    assert result.content == "this should not crash"


@pytest.mark.unit
def test_transcript_hook_concurrent_writes(tmp_path, monkeypatch):
    """Multiple threads writing simultaneously don't corrupt the file."""
    monkeypatch.setenv("PEPPER_VAULT_PATH", str(tmp_path))

    from pepper.pipeline.hooks.transcript import transcript_hook
    from pepper.pipeline.model import PipelineMessage

    errors: list[str] = []
    barrier = threading.Barrier(2)

    def write_batch(prefix: str, count: int) -> None:
        barrier.wait()
        try:
            for i in range(count):
                msg = PipelineMessage(
                    direction="inbound",
                    timestamp=f"2026-04-08T18:{i:02d}:00",
                    source="test",
                    chat_id=f"test-{prefix}-{i}",
                    sender=prefix,
                    content=f"{prefix} message {i}",
                )
                transcript_hook(msg)
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=write_batch, args=("thread1", 10))
    t2 = threading.Thread(target=write_batch, args=("thread2", 10))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0, f"Errors: {errors}"

    raw_dir = tmp_path / "daily" / "raw"
    jsonl_files = list(raw_dir.glob("*.jsonl"))
    lines = jsonl_files[0].read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 20

    # Every line is valid JSON
    for line in lines:
        parsed = json.loads(line)
        assert "content" in parsed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_transcript_hook.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pepper.pipeline.hooks.transcript'`

- [ ] **Step 3: Implement the transcript hook**

```python
# src/pepper/pipeline/hooks/transcript.py
"""Transcript hook — appends conversation-level JSONL to daily raw log."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from filelock import FileLock

from pepper.hooks.shared import get_vault_path
from pepper.pipeline.model import PipelineMessage

log = logging.getLogger("pepper-pipeline")


def _get_transcript_path() -> Path:
    """Return today's JSONL transcript path."""
    vault = get_vault_path()
    today = datetime.now().strftime("%Y-%m-%d")
    return vault / "daily" / "raw" / f"{today}.jsonl"


def transcript_hook(message: PipelineMessage) -> PipelineMessage:
    """Append message to today's JSONL transcript. Never blocks delivery."""
    try:
        path = _get_transcript_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(".jsonl.lock")

        line = message.to_transcript_json() + "\n"

        with FileLock(lock_path):
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception as exc:
        log.warning(f"Transcript write failed: {exc}")

    return message
```

- [ ] **Step 4: Register the hook in the hook lists**

Update `src/pepper/pipeline/hooks/__init__.py`:

```python
"""Pipeline hook registration — lists of hooks for inbound and outbound messages."""

from __future__ import annotations

from pepper.pipeline.hooks.transcript import transcript_hook
from pepper.pipeline.runner import Hook

# Hooks are called in order. Each receives the message from the previous hook.
# Return None from a hook to drop the message.
INBOUND_HOOKS: list[Hook] = [transcript_hook]
OUTBOUND_HOOKS: list[Hook] = [transcript_hook]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_transcript_hook.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/pepper/pipeline/hooks/transcript.py src/pepper/pipeline/hooks/__init__.py tests/unit/test_transcript_hook.py
git commit -m "feat: add transcript hook — JSONL daily log writer"
```

---

### Task 4: Wire Pipeline into Channel Server

**Files:**
- Modify: `src/pepper/channel/server.py:208-248` (inbound)
- Modify: `src/pepper/channel/server.py:397-420` (outbound)

- [ ] **Step 1: Run existing channel server tests to confirm baseline**

Run: `uv run pytest tests/unit/test_channel_router.py tests/integration/test_channel_http.py tests/integration/test_channel_routing.py -v`
Expected: All pass

- [ ] **Step 2: Wire pipeline into inbound message handler**

In `src/pepper/channel/server.py`, add import at the top (after existing imports, around line 28):

```python
from pepper.pipeline import run_inbound, run_outbound
from pepper.pipeline.model import PipelineMessage
```

In `_handle_message` (line 208), after line 227 (`router.add(chat_id, source)`) and before the meta dict construction (line 229), add pipeline call:

```python
async def _handle_message(
    router: Router,
    receive: ASGIReceive,
    send: ASGISend,
) -> None:
    """Handle POST /message."""
    body = await _read_body(receive)
    data = json.loads(body)
    source = data.get("source")
    chat_id = data.get("chat_id")
    content = data.get("content")
    if not source or not chat_id or not content:
        await _json_response(
            send,
            400,
            {"error": "source, chat_id, and content are required"},
        )
        return

    router.add(chat_id, source)

    # --- Pipeline: run inbound hooks ---
    pipeline_msg = PipelineMessage(
        direction="inbound",
        timestamp=datetime.now(UTC).isoformat(),
        source=source,
        chat_id=chat_id,
        sender=data.get("sender", "unknown"),
        content=content,
        metadata={k: str(v) for k, v in data.get("metadata", {}).items()},
    )
    result = await asyncio.to_thread(run_inbound, pipeline_msg)
    if result is None:
        await _json_response(
            send, 200, {"status": "dropped", "chat_id": chat_id}
        )
        return
    # Use potentially-transformed content from pipeline
    content = result.content
    # --- End pipeline ---

    meta = {
        "chat_id": chat_id,
        "sender": data.get("sender", "unknown"),
        "integration": source,
    }
    for k, v in data.get("metadata", {}).items():
        meta[k] = str(v)

    _enqueue_notification(content, meta)

    emit_to_source(
        source,
        {"chat_id": chat_id, "content": content, "meta": meta},
    )
    await _json_response(
        send,
        200,
        {"status": "queued", "chat_id": chat_id},
    )
```

- [ ] **Step 3: Wire pipeline into outbound reply handler**

In `handle_call_tool` (line 398), after constructing `reply_data` (line 417) and before `emit_to_source` (line 418):

```python
    @server.call_tool()  # type: ignore[untyped-decorator]
    async def handle_call_tool(
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> list[types.TextContent]:
        if name != "reply":
            raise ValueError(f"unknown tool: {name}")

        arguments = arguments or {}
        chat_id = arguments.get("chat_id", "")
        text = arguments.get("text", "")
        metadata = arguments.get("metadata", {})

        source = router.lookup(chat_id) or "unknown"

        # --- Pipeline: run outbound hooks ---
        pipeline_msg = PipelineMessage(
            direction="outbound",
            timestamp=datetime.now(UTC).isoformat(),
            source=source,
            chat_id=chat_id,
            sender="Pepper",
            content=text,
            metadata={k: str(v) for k, v in metadata.items()},
        )
        result = await asyncio.to_thread(run_outbound, pipeline_msg)
        if result is None:
            return [types.TextContent(type="text", text="dropped by pipeline")]
        text = result.content
        # --- End pipeline ---

        reply_data = {
            "chat_id": chat_id,
            "text": text,
            "metadata": metadata,
            "source": source,
            "ts": datetime.now(UTC).isoformat(),
        }
        emit_to_source(source, reply_data)

        return [types.TextContent(type="text", text="sent")]
```

- [ ] **Step 4: Run existing channel server tests to verify nothing broke**

Run: `uv run pytest tests/unit/test_channel_router.py tests/integration/test_channel_http.py tests/integration/test_channel_routing.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/pepper/channel/server.py
git commit -m "feat: wire pipeline hooks into channel server inbound/outbound"
```

---

### Task 5: Strip `hooks/shared.py`

**Files:**
- Modify: `src/pepper/hooks/shared.py`
- Modify: `tests/unit/test_shared.py`
- Modify: `tests/unit/test_hooks_shared.py`

- [ ] **Step 1: Update `hooks/shared.py` to keep only vault path utilities**

Replace the entire contents of `src/pepper/hooks/shared.py` with:

```python
"""Shared utilities for Pepper — vault path resolution."""

import os
from datetime import datetime
from pathlib import Path


def get_vault_path() -> Path:
    """Return the absolute path to the Memory vault.

    Uses PEPPER_VAULT_PATH env var if set, otherwise defaults to ~/.pepper/Memory.
    """
    override = os.environ.get("PEPPER_VAULT_PATH")
    if override:
        return Path(override)
    return Path.home() / ".pepper" / "Memory"


def get_daily_log_path(vault_path: Path) -> Path:
    """Return today's raw daily log path: Memory/daily/raw/YYYY-MM-DD.jsonl."""
    today = datetime.now().strftime("%Y-%m-%d")
    return vault_path / "daily" / "raw" / f"{today}.jsonl"
```

- [ ] **Step 2: Update `tests/unit/test_shared.py`**

Replace the entire contents with:

```python
"""Tests for hook shared utilities."""

from pepper.hooks.shared import get_daily_log_path, get_vault_path


def test_get_vault_path():
    vault = get_vault_path()
    assert vault.name == "Memory"


def test_get_daily_log_path(temp_vault):
    path = get_daily_log_path(temp_vault)
    assert path.parent.name == "raw"
    assert path.suffix == ".jsonl"
    assert path.stem.count("-") == 2
```

- [ ] **Step 3: Update `tests/unit/test_hooks_shared.py`**

Replace the entire contents with:

```python
"""Tests for pepper.hooks.shared — vault path resolution."""

from pathlib import Path

from pepper.hooks.shared import get_vault_path


def test_vault_path_from_env(tmp_path, monkeypatch):
    """PEPPER_VAULT_PATH env var overrides default."""
    vault = tmp_path / "Memory"
    vault.mkdir()
    monkeypatch.setenv("PEPPER_VAULT_PATH", str(vault))
    assert get_vault_path() == vault


def test_vault_path_default(monkeypatch):
    """Default vault path is ~/.pepper/Memory."""
    monkeypatch.delenv("PEPPER_VAULT_PATH", raising=False)
    expected = Path.home() / ".pepper" / "Memory"
    assert get_vault_path() == expected
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_shared.py tests/unit/test_hooks_shared.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pepper/hooks/shared.py tests/unit/test_shared.py tests/unit/test_hooks_shared.py
git commit -m "refactor: strip hooks/shared.py to vault path utilities only"
```

---

### Task 6: Delete Old Session Hooks

**Files:**
- Delete: `src/pepper/hooks/session_start_context.py`
- Delete: `src/pepper/hooks/pre_compact_flush.py`
- Delete: `src/pepper/hooks/session_end_flush.py`
- Delete: `tests/integration/test_session_start.py`
- Delete: `tests/integration/test_session_end.py`
- Delete: `tests/integration/test_pre_compact.py`

- [ ] **Step 1: Delete the hook files**

```bash
rm src/pepper/hooks/session_start_context.py
rm src/pepper/hooks/pre_compact_flush.py
rm src/pepper/hooks/session_end_flush.py
```

- [ ] **Step 2: Delete the hook tests**

```bash
rm tests/integration/test_session_start.py
rm tests/integration/test_session_end.py
rm tests/integration/test_pre_compact.py
```

- [ ] **Step 3: Clean up conftest.py**

Remove the `mock_stdin_data` fixture (lines 141-156) and `temp_transcript` fixture (lines 159-170) from `tests/conftest.py`. These are only used by the deleted hook tests. The new contents of those lines should be empty — just remove the two fixture definitions and any blank lines they leave behind.

- [ ] **Step 4: Run all tests to verify nothing is broken**

Run: `uv run pytest -m unit -v`
Expected: All pass (hook tests gone, remaining tests still work)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: delete old session hooks and their tests"
```

---

### Task 7: Update Init Templates

**Files:**
- Modify: `src/pepper/init/templates/settings.json.j2`
- Modify: `src/pepper/init/templates/CLAUDE.md.j2`

- [ ] **Step 1: Update settings.json.j2 to remove hooks**

Replace the entire contents of `src/pepper/init/templates/settings.json.j2` with:

```json
{
  "permissions": {
    "defaultMode": "bypassPermissions",
    "allow": [
      "Bash",
      "Read",
      "Edit",
      "Write",
      "Glob",
      "Grep"
    ]
  }
}
```

- [ ] **Step 2: Update CLAUDE.md.j2 with vault read directive**

Replace the entire contents of `src/pepper/init/templates/CLAUDE.md.j2` with:

```markdown
# Pepper

You are **Pepper** 🌶️, Jeff Richley's Second Brain & Executive Assistant.

## Core Files

Your identity, personality, and operational knowledge live in the Memory/ vault.
At the start of every session, read these files:

| File | Purpose |
|------|---------|
| `Memory/IDENTITY.md` | Your name, role, emoji |
| `Memory/SOUL.md` | Personality, behavioral rules, hard boundaries, priorities |
| `Memory/USER.md` | Jeff's profile, platforms, drafting criteria |
| `Memory/MEMORY.md` | Curated long-term memory (active projects, decisions, notes) |
| `Memory/OPERATIONS.md` | Vault map, search commands, project conventions, schedules |

Also read the most recent 2 daily summaries from `Memory/daily/summaries/` for recent context.

## Hard Boundaries

- NEVER send emails or messages without explicit permission
- NEVER access financial data or make purchases
- NEVER delete anything without explicit permission

## Vault Search

Use pyqmd for semantic search across the vault:

```bash
uv run qmd search "query" -c vault
uv run qmd search "query" -c vault --path-prefix projects/niwc
```

## Daily Transcript

Conversations are automatically captured to `Memory/daily/raw/YYYY-MM-DD.jsonl` by the channel server pipeline. Do not write to these files manually.

The nightly reflection job (3 AM) summarizes the day's transcript into `Memory/daily/summaries/`.

## Projects

Each project has a `STATUS.md` in `Memory/projects/`. Check there for current focus, blockers, and next steps.
```

- [ ] **Step 3: Run init tests to check for breakage**

Run: `uv run pytest tests/unit/test_init.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/pepper/init/templates/settings.json.j2 src/pepper/init/templates/CLAUDE.md.j2
git commit -m "chore: remove hook config from templates, add vault read directive"
```

---

### Task 8: Update Nightly Reflection Job

**Files:**
- Modify: `src/pepper/scheduler/jobs.yaml:24-34`

- [ ] **Step 1: Update the nightly reflection prompt**

Replace lines 24-34 in `src/pepper/scheduler/jobs.yaml` (the `nightly_reflection` entry) with:

```yaml
nightly_reflection:
  trigger: cron
  schedule:
    hour: 3
    minute: 0
  prompt: >
    Nightly reflection: Read today's transcript from Memory/daily/raw/ (the
    most recent .jsonl file). Each line is a JSON object with fields: ts
    (timestamp), dir (inbound/outbound), src (source like discord), cid
    (chat_id), sender, and content. Summarize the day's conversations into
    Memory/daily/summaries/YYYY-MM-DD.md. Identify patterns, decisions made,
    and open loops. Send a brief summary to pepper-chat Discord channel.
  channel_hint: "#pepper-chat"
```

- [ ] **Step 2: Verify YAML is valid**

Run: `uv run python -c "import yaml; yaml.safe_load(open('src/pepper/scheduler/jobs.yaml'))"`
Expected: No error

- [ ] **Step 3: Commit**

```bash
git add src/pepper/scheduler/jobs.yaml
git commit -m "chore: update nightly reflection to read JSONL transcripts"
```

---

### Task 9: Run Full Gate

- [ ] **Step 1: Run the full quality gate**

Run: `just gate`
Expected: All checks pass — lint, format, mypy, xenon, pip-audit, pytest with coverage.

- [ ] **Step 2: Fix any issues**

If xenon reports complexity issues in `server.py` from the pipeline additions, extract the pipeline construction into a helper function (e.g., `_build_inbound_message()` and `_build_outbound_message()`).

If mypy reports type issues, add appropriate type annotations.

If coverage drops below threshold, verify that new pipeline tests are being collected.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: address gate issues from pipeline integration"
```

- [ ] **Step 4: Run gate again to confirm clean**

Run: `just gate`
Expected: All pass

---

## Self-Review

**Spec coverage check:**

| Spec Section | Task |
|---|---|
| 1. Data Model (PipelineMessage) | Task 1 |
| 2. Package Structure | Tasks 1, 2, 3 |
| 3. Pipeline Runner | Task 2 |
| 4. Transcript Hook | Task 3 |
| 5. Channel Server Integration | Task 4 |
| 6. Removals — hook files | Task 6 |
| 6. Removals — shared.py strip | Task 5 |
| 6. Removals — tests | Task 6 |
| 6. Removals — config template | Task 7 |
| 7. Nightly Reflection Update | Task 8 |
| 8. Runtime CLAUDE.md Update | Task 7 |
| 9. Testing | Tasks 1, 2, 3 (unit), Task 9 (gate) |
| 10. What This Does NOT Cover | N/A (correctly scoped out) |

**Placeholder scan:** No TBDs, TODOs, or vague instructions found.

**Type consistency:** `PipelineMessage` used consistently across all tasks. `run_hooks`, `run_inbound`, `run_outbound` signatures match. `Hook` type alias defined once in `runner.py`, imported in `hooks/__init__.py`. `transcript_hook` signature matches `Hook` type. `to_transcript_json()` defined in Task 1, used in Task 3.
