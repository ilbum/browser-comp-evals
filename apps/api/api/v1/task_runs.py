from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import TaskRunRow
from api.db.session import get_session

router = APIRouter()


class TaskRunResponse(BaseModel):
    id: str
    eval_run_id: str
    task_id: str
    status: str
    final_answer: str | None
    expected_answer: str
    is_correct: bool | None
    score: float | None
    stats: dict[str, Any]
    error_type: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


def _row_to_response(row: TaskRunRow) -> TaskRunResponse:
    return TaskRunResponse(
        id=str(row.id),
        eval_run_id=str(row.eval_run_id),
        task_id=row.task_id,
        status=row.status,
        final_answer=row.final_answer,
        expected_answer=row.expected_answer,
        is_correct=row.is_correct,
        score=row.score,
        stats=row.stats or {},
        error_type=row.error_type,
        error_message=row.error_message,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


@router.get("/eval-runs/{eval_run_id}/task-runs", response_model=list[TaskRunResponse])
async def list_task_runs(
    eval_run_id: str, session: AsyncSession = Depends(get_session)
) -> list[TaskRunResponse]:
    result = await session.execute(
        select(TaskRunRow).where(TaskRunRow.eval_run_id == uuid.UUID(eval_run_id))
    )
    rows = result.scalars().all()
    return [_row_to_response(r) for r in rows]


@router.get("/task-runs/{task_run_id}", response_model=TaskRunResponse)
async def get_task_run(
    task_run_id: str, session: AsyncSession = Depends(get_session)
) -> TaskRunResponse:
    row = await session.get(TaskRunRow, uuid.UUID(task_run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="TaskRun not found")
    return _row_to_response(row)
