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
