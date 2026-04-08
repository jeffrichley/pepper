"""Pipeline hook runner — executes hooks in sequence on a message."""

from __future__ import annotations

from collections.abc import Callable

from pepper.pipeline.model import PipelineMessage

Hook = Callable[[PipelineMessage], PipelineMessage | None]


def run_hooks(
    hooks: list[Hook],
    message: PipelineMessage,
) -> PipelineMessage | None:
    """Run hooks in sequence. Returns None if any hook drops the message.

    Args:
        hooks: Ordered list of hook callables to apply.
        message: The pipeline message to process.

    Returns:
        The (possibly transformed) message, or None if a hook dropped it.
    """
    for hook in hooks:
        result = hook(message)
        if result is None:
            return None
        message = result
    return message
