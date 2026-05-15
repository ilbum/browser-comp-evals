from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvalTask(BaseModel):
    id: str
    benchmark: Literal["browsecomp"]
    question: str
    expected_answer: str
    metadata: dict[str, Any] = {}


class EvalRun(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    benchmark: str
    agent_name: str
    agent_version: str
    model_name: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"] = "queued"
    task_count: int
    config: dict[str, Any] = {}
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TaskRun(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    eval_run_id: uuid.UUID
    task_id: str
    status: Literal["queued", "running", "answered", "graded", "failed", "timed_out"] = "queued"
    final_answer: str | None = None
    expected_answer: str
    is_correct: bool | None = None
    score: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_type: str | None = None
    error_message: str | None = None


class EvidenceItem(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None
    relevance_note: str | None = None


class TaskRunStats(BaseModel):
    search_calls: int = 0
    page_opens: int = 0
    extracted_passages: int = 0
    candidate_answers_generated: int = 0
    verification_attempts: int = 0
    runtime_seconds: float = 0.0
    tool_error_count: int = 0
    budget_exhausted: bool = False


class AgentResult(BaseModel):
    final_answer: str | None = None
    confidence: float | None = None
    answer_rationale: str | None = None
    evidence: list[EvidenceItem] = []
    stats: TaskRunStats = Field(default_factory=TaskRunStats)


class EvalRunMetrics(BaseModel):
    total_tasks: int
    completed_tasks: int
    correct_tasks: int
    incorrect_tasks: int
    timed_out_tasks: int
    failed_tasks: int
    accuracy: float
    avg_runtime_seconds: float
    avg_search_calls: float
    avg_page_opens: float
    avg_tool_errors: float


class TaskBudget(BaseModel):
    max_search_calls: int = 30
    max_page_opens: int = 60
    max_steps: int = 50
    max_runtime_seconds: int = 600


FailureType = Literal[
    "bad_search_strategy",
    "tool_failure",
    "page_fetch_failure",
    "premature_answer",
    "wrong_candidate_selected",
    "verification_failure",
    "budget_exhausted",
    "unknown",
]
