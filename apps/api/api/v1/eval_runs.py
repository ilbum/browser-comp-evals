from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import EvalRunRow, EvalTaskRow, TaskRunRow
from api.db.session import get_session
from api.settings import settings

router = APIRouter()


class StartEvalRunRequest(BaseModel):
    benchmark: str = "browsecomp"
    task_count: int = 10
    agent_name: str = "browse-research-agent"
    agent_version: str = "v1"
    model_name: str = "claude-sonnet-4-6"
    task_ids: list[str] | None = None
    sampling: str = "random"
    config: dict[str, Any] = {}


class EvalRunResponse(BaseModel):
    id: str
    benchmark: str
    agent_name: str
    agent_version: str
    model_name: str
    status: str
    task_count: int
    config: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


@router.post("/eval-runs", response_model=EvalRunResponse, status_code=202)
async def create_eval_run(
    req: StartEvalRunRequest, session: AsyncSession = Depends(get_session)
) -> EvalRunResponse:
    from browsecomp.dataset_loader import sample_tasks

    # Fetch matching task IDs
    result = await session.execute(
        select(EvalTaskRow).where(EvalTaskRow.benchmark == req.benchmark)
    )
    all_tasks = result.scalars().all()

    from eval_core.models import EvalTask
    eval_tasks = [
        EvalTask(
            id=t.id,
            benchmark=t.benchmark,  # type: ignore
            question=t.question,
            expected_answer=t.expected_answer,
            metadata=t.metadata_,
        )
        for t in all_tasks
    ]
    selected = sample_tasks(
        eval_tasks,
        count=req.task_count,
        task_ids=req.task_ids,
        sampling=req.sampling,
    )

    if not selected:
        raise HTTPException(status_code=422, detail="No tasks found matching the criteria")

    run_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    budget = {
        "max_search_calls": req.config.get("max_searches", 30),
        "max_page_opens": req.config.get("max_pages", 60),
        "max_steps": req.config.get("max_agent_steps", 50),
        "max_runtime_seconds": req.config.get("max_runtime_seconds", 600),
    }

    row = EvalRunRow(
        id=run_id,
        benchmark=req.benchmark,
        agent_name=req.agent_name,
        agent_version=req.agent_version,
        model_name=req.model_name,
        status="running",
        task_count=len(selected),
        config={**req.config, "budget": budget, "task_ids": [t.id for t in selected]},
        started_at=now,
        created_at=now,
    )
    session.add(row)
    await session.commit()

    # Fire off Temporal workflow (non-blocking)
    await _start_temporal_workflow(
        eval_run_id=str(run_id),
        task_ids=[t.id for t in selected],
        agent_name=req.agent_name,
        agent_version=req.agent_version,
        model_name=req.model_name,
        budget=budget,
    )

    return EvalRunResponse(
        id=str(row.id),
        benchmark=row.benchmark,
        agent_name=row.agent_name,
        agent_version=row.agent_version,
        model_name=row.model_name,
        status=row.status,
        task_count=row.task_count,
        config=row.config,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


@router.get("/eval-runs/{eval_run_id}", response_model=EvalRunResponse)
async def get_eval_run(
    eval_run_id: str, session: AsyncSession = Depends(get_session)
) -> EvalRunResponse:
    row = await session.get(EvalRunRow, uuid.UUID(eval_run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="EvalRun not found")

    completed = await session.execute(
        select(TaskRunRow).where(
            TaskRunRow.eval_run_id == row.id,
            TaskRunRow.status.in_(["graded", "failed", "timed_out"]),
        )
    )
    config_with_progress = {
        **row.config,
        "completed_task_count": len(completed.scalars().all()),
    }

    return EvalRunResponse(
        id=str(row.id),
        benchmark=row.benchmark,
        agent_name=row.agent_name,
        agent_version=row.agent_version,
        model_name=row.model_name,
        status=row.status,
        task_count=row.task_count,
        config=config_with_progress,
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


async def _start_temporal_workflow(
    eval_run_id: str,
    task_ids: list[str],
    agent_name: str,
    agent_version: str,
    model_name: str,
    budget: dict,
) -> None:
    from temporalio.client import Client
    from temporal_workflows.workflows import BrowseCompEvalWorkflow, EvalRunRequest

    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
    await client.start_workflow(
        BrowseCompEvalWorkflow.run,
        EvalRunRequest(
            eval_run_id=eval_run_id,
            task_ids=task_ids,
            agent_name=agent_name,
            agent_version=agent_version,
            model_name=model_name,
            budget=budget,
        ),
        id=f"eval-run-{eval_run_id}",
        task_queue=settings.temporal_task_queue,
    )
