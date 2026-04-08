"""Pepper message pipeline — hook-based transform chain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pepper.pipeline.hooks import INBOUND_HOOKS, OUTBOUND_HOOKS
from pepper.pipeline.runner import run_hooks

if TYPE_CHECKING:
    from pepper.pipeline.model import PipelineMessage


def run_inbound(message: PipelineMessage) -> PipelineMessage | None:
    """Run all inbound hooks on a message.

    Args:
        message: The inbound pipeline message to process.

    Returns:
        The (possibly transformed) message, or None if a hook dropped it.
    """
    return run_hooks(INBOUND_HOOKS, message)


def run_outbound(message: PipelineMessage) -> PipelineMessage | None:
    """Run all outbound hooks on a message.

    Args:
        message: The outbound pipeline message to process.

    Returns:
        The (possibly transformed) message, or None if a hook dropped it.
    """
    return run_hooks(OUTBOUND_HOOKS, message)
