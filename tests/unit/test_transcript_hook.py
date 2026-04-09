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
    # Create a directory where the JSONL file would go, blocking the write
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
