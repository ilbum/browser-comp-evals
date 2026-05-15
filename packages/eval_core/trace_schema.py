from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


TraceEventType = Literal[
    "agent_thought_summary",
    "search_query",
    "search_results",
    "page_opened",
    "page_extracted",
    "candidate_answer_added",
    "candidate_answer_rejected",
    "verification_attempt",
    "final_answer",
    "tool_error",
]


class TraceEvent(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_run_id: uuid.UUID
    step_index: int
    event_type: TraceEventType
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
