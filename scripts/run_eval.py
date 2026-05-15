#!/usr/bin/env python3
"""CLI runner — start an eval run via the API or directly via Temporal.

Usage:
    python scripts/run_eval.py --benchmark browsecomp --task-count 10
    python scripts/run_eval.py --benchmark browsecomp --task-ids browsecomp_0001 browsecomp_0002
    make eval-browsecomp TASK_COUNT=5
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))

import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(add_completion=False)


@app.command()
def main(
    benchmark: str = typer.Option("browsecomp", help="Benchmark name"),
    task_count: int = typer.Option(10, help="Number of tasks to run"),
    task_ids: Optional[list[str]] = typer.Option(None, help="Specific task IDs"),
    sampling: str = typer.Option("random", help="Sampling strategy: random or first"),
    agent_name: str = typer.Option("browse-research-agent"),
    agent_version: str = typer.Option("v1"),
    model_name: str = typer.Option("claude-sonnet-4-6"),
    max_searches: int = typer.Option(30),
    max_pages: int = typer.Option(60),
    max_runtime_seconds: int = typer.Option(600),
) -> None:
    asyncio.run(
        _run(
            benchmark=benchmark,
            task_count=task_count,
            task_ids=task_ids,
            sampling=sampling,
            agent_name=agent_name,
            agent_version=agent_version,
            model_name=model_name,
            config={
                "max_searches": max_searches,
                "max_pages": max_pages,
                "max_runtime_seconds": max_runtime_seconds,
            },
        )
    )


async def _run(
    benchmark: str,
    task_count: int,
    task_ids: list[str] | None,
    sampling: str,
    agent_name: str,
    agent_version: str,
    model_name: str,
    config: dict,
) -> None:
    from api.db.session import AsyncSessionLocal
    from api.db.models import EvalRunRow, EvalTaskRow, TaskRunRow
    from api.settings import settings
    from browsecomp.dataset_loader import sample_tasks
    from eval_core.models import EvalTask, TaskBudget
    from sqlalchemy import select
    from temporalio.client import Client
    from temporal_workflows.workflows import BrowseCompEvalWorkflow, EvalRunRequest

    console.print(f"\n[bold blue]BrowseComp Eval Runner[/bold blue]")
    console.print(f"Benchmark: {benchmark}  Tasks: {task_count}  Model: {model_name}\n")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(EvalTaskRow).where(EvalTaskRow.benchmark == benchmark)
        )
        all_task_rows = result.scalars().all()

    if not all_task_rows:
        console.print("[red]No tasks found in database. Run `make load-browsecomp` first.[/red]")
        raise typer.Exit(1)

    eval_tasks = [
        EvalTask(id=t.id, benchmark=t.benchmark, question=t.question, expected_answer=t.expected_answer, metadata=t.metadata_)  # type: ignore
        for t in all_task_rows
    ]
    selected = sample_tasks(eval_tasks, count=task_count, task_ids=task_ids, sampling=sampling)
    console.print(f"Selected {len(selected)} tasks")

    budget = {
        "max_search_calls": config.get("max_searches", 30),
        "max_page_opens": config.get("max_pages", 60),
        "max_steps": 50,
        "max_runtime_seconds": config.get("max_runtime_seconds", 600),
    }

    run_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        session.add(EvalRunRow(
            id=run_id,
            benchmark=benchmark,
            agent_name=agent_name,
            agent_version=agent_version,
            model_name=model_name,
            status="running",
            task_count=len(selected),
            config={**config, "budget": budget, "task_ids": [t.id for t in selected]},
            started_at=now,
            created_at=now,
        ))
        await session.commit()

    console.print(f"Created eval run: [bold]{run_id}[/bold]")

    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
    handle = await client.start_workflow(
        BrowseCompEvalWorkflow.run,
        EvalRunRequest(
            eval_run_id=str(run_id),
            task_ids=[t.id for t in selected],
            agent_name=agent_name,
            agent_version=agent_version,
            model_name=model_name,
            budget=budget,
        ),
        id=f"eval-run-{run_id}",
        task_queue=settings.temporal_task_queue,
    )

    console.print("Workflow started. Waiting for completion...\n")
    start = time.monotonic()

    result = await handle.result()

    elapsed = time.monotonic() - start
    metrics = result.metrics

    # Print summary
    console.print("\n[bold green]BrowseComp Eval Run Complete[/bold green]\n")
    table = Table(show_header=False, box=None)
    table.add_row("Tasks evaluated:", str(metrics["total_tasks"]))
    table.add_row("Correct:", str(metrics["correct_tasks"]))
    table.add_row("Incorrect:", str(metrics["incorrect_tasks"]))
    table.add_row("Failed:", str(metrics["failed_tasks"]))
    table.add_row("Timed out:", str(metrics["timed_out_tasks"]))
    table.add_row("Accuracy:", f"{metrics['accuracy']:.1%}")
    table.add_row("Wall time:", f"{elapsed:.0f}s")
    console.print(table)

    # Per-task stats from DB
    async with AsyncSessionLocal() as session:
        rows_result = await session.execute(
            select(TaskRunRow).where(TaskRunRow.eval_run_id == run_id)
        )
        task_rows = rows_result.scalars().all()

    if task_rows:
        stats_dicts = [r.stats for r in task_rows if r.stats]
        if stats_dicts:
            avg = lambda key: sum(s.get(key, 0) for s in stats_dicts) / len(stats_dicts)
            console.print("\n[bold]Average per task:[/bold]")
            console.print(f"  Runtime:       {avg('runtime_seconds'):.1f}s")
            console.print(f"  Search calls:  {avg('search_calls'):.1f}")
            console.print(f"  Pages opened:  {avg('page_opens'):.1f}")
            console.print(f"  Tool errors:   {avg('tool_error_count'):.1f}")

    console.print(f"\nArtifacts saved in database under run ID: [bold]{run_id}[/bold]")
    console.print(f"Inspect: python scripts/show_eval_run.py --eval-run-id {run_id}")


if __name__ == "__main__":
    app()
