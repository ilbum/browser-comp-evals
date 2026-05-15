"""Temporal activities for the BrowseComp eval harness."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from temporalio import activity

from eval_core.grading import grade_answer
from eval_core.models import AgentResult, EvalTask, TaskBudget, TaskRunStats


# ── Data transfer objects ─────────────────────────────────────────────────────

class LoadTaskInput:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id


class RunAgentInput:
    def __init__(
        self,
        task: dict,
        task_run_id: str,
        budget: dict,
        agent_name: str,
        agent_version: str,
        model_name: str,
    ) -> None:
        self.task = task
        self.task_run_id = task_run_id
        self.budget = budget
        self.agent_name = agent_name
        self.agent_version = agent_version
        self.model_name = model_name


class GradeAnswerInput:
    def __init__(self, predicted: str | None, expected: str) -> None:
        self.predicted = predicted
        self.expected = expected


class PersistResultInput:
    def __init__(
        self,
        task_run_id: str,
        status: str,
        final_answer: str | None,
        is_correct: bool | None,
        score: float | None,
        stats: dict,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.task_run_id = task_run_id
        self.status = status
        self.final_answer = final_answer
        self.is_correct = is_correct
        self.score = score
        self.stats = stats
        self.error_type = error_type
        self.error_message = error_message


class PersistTraceInput:
    def __init__(self, task_run_id: str, events: list[dict]) -> None:
        self.task_run_id = task_run_id
        self.events = events


# ── Activities ────────────────────────────────────────────────────────────────

@activity.defn(name="load_task")
async def load_task_activity(task_id: str) -> dict:
    from api.db.session import AsyncSessionLocal
    from api.db.models import EvalTaskRow
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        row = await session.get(EvalTaskRow, task_id)
        if row is None:
            raise ValueError(f"Task not found: {task_id}")
        return {
            "id": row.id,
            "benchmark": row.benchmark,
            "question": row.question,
            "expected_answer": row.expected_answer,
            "metadata": row.metadata_,
        }


@activity.defn(name="create_task_run")
async def create_task_run_activity(
    eval_run_id: str, task_id: str, expected_answer: str
) -> str:
    from api.db.session import AsyncSessionLocal
    from api.db.models import TaskRunRow

    task_run_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        session.add(
            TaskRunRow(
                id=uuid.UUID(task_run_id),
                eval_run_id=uuid.UUID(eval_run_id),
                task_id=task_id,
                status="running",
                expected_answer=expected_answer,
                started_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
    return task_run_id


@activity.defn(name="run_browse_agent")
async def run_browse_agent_activity(
    task: dict,
    task_run_id: str,
    budget: dict,
    agent_name: str,
    model_name: str,
) -> dict:
    from agents.base import RunContext
    from agents.browse_research_agent.agent import BrowseResearchAgentV1

    eval_task = EvalTask(**task)
    task_budget = TaskBudget(**budget)
    ctx = RunContext(task_run_id=task_run_id, budget=task_budget)

    agent = BrowseResearchAgentV1(model=model_name)
    result: AgentResult = await agent.run_task(eval_task, ctx)

    return {
        "final_answer": result.final_answer,
        "confidence": result.confidence,
        "answer_rationale": result.answer_rationale,
        "evidence": [e.model_dump() for e in result.evidence],
        "stats": result.stats.model_dump(),
        "trace_events": ctx.trace_events,
    }


@activity.defn(name="grade_answer")
async def grade_answer_activity(predicted: str | None, expected: str) -> dict:
    result = grade_answer(predicted, expected)
    return result.model_dump()


@activity.defn(name="persist_task_result")
async def persist_task_result_activity(
    task_run_id: str,
    status: str,
    final_answer: str | None,
    is_correct: bool | None,
    score: float | None,
    stats: dict,
    error_type: str | None = None,
    error_message: str | None = None,
) -> None:
    from api.db.session import AsyncSessionLocal
    from api.db.models import TaskRunRow

    async with AsyncSessionLocal() as session:
        row = await session.get(TaskRunRow, uuid.UUID(task_run_id))
        if row is None:
            raise ValueError(f"TaskRun not found: {task_run_id}")
        row.status = status
        row.final_answer = final_answer
        row.is_correct = is_correct
        row.score = score
        row.stats = stats
        row.error_type = error_type
        row.error_message = error_message
        row.completed_at = datetime.now(timezone.utc)
        await session.commit()


@activity.defn(name="persist_trace_events")
async def persist_trace_events_activity(task_run_id: str, events: list[dict]) -> None:
    from api.db.session import AsyncSessionLocal
    from api.db.models import TraceEventRow

    if not events:
        return

    async with AsyncSessionLocal() as session:
        for evt in events:
            session.add(
                TraceEventRow(
                    id=uuid.uuid4(),
                    task_run_id=uuid.UUID(task_run_id),
                    step_index=evt["step_index"],
                    event_type=evt["event_type"],
                    payload=evt["payload"],
                    created_at=datetime.now(timezone.utc),
                )
            )
        await session.commit()


@activity.defn(name="finalize_eval_run")
async def finalize_eval_run_activity(eval_run_id: str, metrics: dict) -> None:
    from api.db.session import AsyncSessionLocal
    from api.db.models import EvalRunRow

    async with AsyncSessionLocal() as session:
        row = await session.get(EvalRunRow, uuid.UUID(eval_run_id))
        if row is None:
            raise ValueError(f"EvalRun not found: {eval_run_id}")
        row.status = "completed"
        row.completed_at = datetime.now(timezone.utc)
        # store metrics in config field for now
        row.config = {**row.config, "final_metrics": metrics}
        await session.commit()
