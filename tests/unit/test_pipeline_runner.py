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
