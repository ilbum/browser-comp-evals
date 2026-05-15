from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import TaskRunRow, TraceEventRow
from api.db.session import get_session

router = APIRouter()


class TraceEventResponse(BaseModel):
    id: str
    task_run_id: str
    step_index: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


@router.get("/task-runs/{task_run_id}/trace", response_model=list[TraceEventResponse])
async def get_task_trace(
    task_run_id: str, session: AsyncSession = Depends(get_session)
) -> list[TraceEventResponse]:
    row = await session.get(TaskRunRow, uuid.UUID(task_run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="TaskRun not found")

    result = await session.execute(
        select(TraceEventRow)
        .where(TraceEventRow.task_run_id == uuid.UUID(task_run_id))
        .order_by(TraceEventRow.step_index)
    )
    events = result.scalars().all()
    return [
        TraceEventResponse(
            id=str(e.id),
            task_run_id=str(e.task_run_id),
            step_index=e.step_index,
            event_type=e.event_type,
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]
