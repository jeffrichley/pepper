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
