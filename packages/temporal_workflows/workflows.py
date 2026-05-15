"""Temporal workflows for the BrowseComp eval harness."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_workflows.activities import (
        create_task_run_activity,
        finalize_eval_run_activity,
        grade_answer_activity,
        load_task_activity,
        persist_task_result_activity,
        persist_trace_events_activity,
        run_browse_agent_activity,
    )


# ── DTOs ─────────────────────────────────────────────────────────────────────

@dataclass
class EvalRunRequest:
    eval_run_id: str
    task_ids: list[str]
    agent_name: str
    agent_version: str
    model_name: str
    budget: dict[str, Any]
    max_concurrency: int = 5


@dataclass
class EvalRunResult:
    eval_run_id: str
    metrics: dict[str, Any]


@dataclass
class TaskRunRequest:
    eval_run_id: str
    task_id: str
    agent_name: str
    model_name: str
    budget: dict[str, Any]


@dataclass
class TaskRunResult:
    task_run_id: str
    task_id: str
    status: str
    is_correct: bool | None
    score: float | None


# ── Retry policies ────────────────────────────────────────────────────────────

_LOAD_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2))
_AGENT_RETRY = RetryPolicy(maximum_attempts=1)
_GRADE_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2))
_PERSIST_RETRY = RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=1))


# ── Per-task workflow ─────────────────────────────────────────────────────────

@workflow.defn(name="BrowseCompTaskWorkflow")
class BrowseCompTaskWorkflow:
    @workflow.run
    async def run(self, req: TaskRunRequest) -> TaskRunResult:
        # 1. Load task
        task = await workflow.execute_activity(
            load_task_activity,
            req.task_id,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=_LOAD_RETRY,
        )

        # 2. Create task run record
        task_run_id = await workflow.execute_activity(
            create_task_run_activity,
            args=[req.eval_run_id, req.task_id, task["expected_answer"]],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=_PERSIST_RETRY,
        )

        # 3. Run agent
        agent_result: dict[str, Any] | None = None
        error_type: str | None = None
        error_message: str | None = None
        try:
            agent_result = await workflow.execute_activity(
                run_browse_agent_activity,
                args=[task, task_run_id, req.budget, req.agent_name, req.model_name],
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=_AGENT_RETRY,
            )
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc)

        # 4. Grade answer
        grading: dict[str, Any] = {"is_correct": False, "score": 0.0, "strategy": "error"}
        if agent_result is not None:
            grading = await workflow.execute_activity(
                grade_answer_activity,
                args=[agent_result.get("final_answer"), task["expected_answer"]],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_GRADE_RETRY,
            )

        # 5. Persist trace events
        if agent_result and agent_result.get("trace_events"):
            await workflow.execute_activity(
                persist_trace_events_activity,
                args=[task_run_id, agent_result["trace_events"]],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=_PERSIST_RETRY,
            )

        # 6. Persist final result
        status = "graded" if agent_result else ("timed_out" if "timeout" in (error_type or "").lower() else "failed")
        await workflow.execute_activity(
            persist_task_result_activity,
            args=[
                task_run_id,
                status,
                agent_result.get("final_answer") if agent_result else None,
                grading["is_correct"],
                grading["score"],
                agent_result["stats"] if agent_result else {},
                error_type,
                error_message,
            ],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_PERSIST_RETRY,
        )

        return TaskRunResult(
            task_run_id=task_run_id,
            task_id=req.task_id,
            status=status,
            is_correct=grading["is_correct"],
            score=grading["score"],
        )


# ── Batch workflow ────────────────────────────────────────────────────────────

@workflow.defn(name="BrowseCompEvalWorkflow")
class BrowseCompEvalWorkflow:
    @workflow.run
    async def run(self, req: EvalRunRequest) -> EvalRunResult:
        semaphore = asyncio.Semaphore(req.max_concurrency)
        results: list[TaskRunResult] = []

        async def run_one(task_id: str) -> TaskRunResult:
            async with semaphore:
                return await workflow.execute_child_workflow(
                    BrowseCompTaskWorkflow,
                    TaskRunRequest(
                        eval_run_id=req.eval_run_id,
                        task_id=task_id,
                        agent_name=req.agent_name,
                        model_name=req.model_name,
                        budget=req.budget,
                    ),
                    id=f"{req.eval_run_id}-task-{task_id}",
                    task_queue="browsecomp-eval",
                    execution_timeout=timedelta(minutes=20),
                )

        child_tasks = [asyncio.create_task(run_one(tid)) for tid in req.task_ids]
        results = await asyncio.gather(*child_tasks, return_exceptions=False)

        total = len(results)
        correct = sum(1 for r in results if r.is_correct)
        failed = sum(1 for r in results if r.status == "failed")
        timed_out = sum(1 for r in results if r.status == "timed_out")
        graded = total - failed - timed_out

        metrics = {
            "total_tasks": total,
            "graded_tasks": graded,
            "correct_tasks": correct,
            "incorrect_tasks": graded - correct,
            "failed_tasks": failed,
            "timed_out_tasks": timed_out,
            "accuracy": correct / graded if graded else 0.0,
        }

        await workflow.execute_activity(
            finalize_eval_run_activity,
            args=[req.eval_run_id, metrics],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_PERSIST_RETRY,
        )

        return EvalRunResult(eval_run_id=req.eval_run_id, metrics=metrics)
