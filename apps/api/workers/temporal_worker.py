"""Temporal worker process — registers all workflows and activities."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps"))

from temporalio.client import Client
from temporalio.worker import Worker

from api.settings import settings
from temporal_workflows.activities import (
    create_task_run_activity,
    finalize_eval_run_activity,
    grade_answer_activity,
    load_task_activity,
    persist_task_result_activity,
    persist_trace_events_activity,
    run_browse_agent_activity,
)
from temporal_workflows.workflows import BrowseCompEvalWorkflow, BrowseCompTaskWorkflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Connecting to Temporal at %s", settings.temporal_host)
    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[BrowseCompEvalWorkflow, BrowseCompTaskWorkflow],
        activities=[
            load_task_activity,
            create_task_run_activity,
            run_browse_agent_activity,
            grade_answer_activity,
            persist_task_result_activity,
            persist_trace_events_activity,
            finalize_eval_run_activity,
        ],
    )

    logger.info("Worker started on queue: %s", settings.temporal_task_queue)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
