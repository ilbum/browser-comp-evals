#!/usr/bin/env python3
"""Inspect a completed eval run.

Usage:
    python scripts/show_eval_run.py --eval-run-id <uuid>
    make show-run RUN_ID=<uuid>
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

console = Console()
app = typer.Typer(add_completion=False)


@app.command()
def main(eval_run_id: str = typer.Option(..., help="UUID of the eval run to inspect")) -> None:
    asyncio.run(_show(eval_run_id))


async def _show(eval_run_id: str) -> None:
    from api.db.session import AsyncSessionLocal
    from api.db.models import EvalRunRow, TaskRunRow

    async with AsyncSessionLocal() as session:
        run = await session.get(EvalRunRow, uuid.UUID(eval_run_id))
        if run is None:
            console.print(f"[red]Eval run not found: {eval_run_id}[/red]")
            raise typer.Exit(1)

        result = await session.execute(
            select(TaskRunRow)
            .where(TaskRunRow.eval_run_id == uuid.UUID(eval_run_id))
            .order_by(TaskRunRow.created_at)
        )
        task_rows = result.scalars().all()

    console.print(f"\n[bold blue]Eval Run: {eval_run_id}[/bold blue]")
    console.print(f"Benchmark:  {run.benchmark}")
    console.print(f"Agent:      {run.agent_name} {run.agent_version}")
    console.print(f"Model:      {run.model_name}")
    console.print(f"Status:     {run.status}")
    console.print(f"Tasks:      {run.task_count}")
    if run.started_at:
        console.print(f"Started:    {run.started_at.isoformat()}")
    if run.completed_at:
        console.print(f"Completed:  {run.completed_at.isoformat()}")

    metrics = run.config.get("final_metrics", {})
    if metrics:
        console.print(f"\n[bold]Metrics[/bold]")
        console.print(f"  Accuracy:  {metrics.get('accuracy', 0):.1%}")
        console.print(f"  Correct:   {metrics.get('correct_tasks', 0)}")
        console.print(f"  Incorrect: {metrics.get('incorrect_tasks', 0)}")
        console.print(f"  Failed:    {metrics.get('failed_tasks', 0)}")

    if task_rows:
        console.print(f"\n[bold]Task Runs[/bold]")
        table = Table("task_id", "status", "correct", "answer", "expected", "searches", "pages")
        for r in task_rows:
            stats = r.stats or {}
            table.add_row(
                r.task_id,
                r.status,
                "✓" if r.is_correct else ("?" if r.is_correct is None else "✗"),
                (r.final_answer or "")[:40],
                r.expected_answer[:40],
                str(stats.get("search_calls", "-")),
                str(stats.get("page_opens", "-")),
            )
        console.print(table)

        failed = [r for r in task_rows if r.status in ("failed", "timed_out")]
        if failed:
            console.print(f"\n[bold red]Failures[/bold red]")
            for r in failed:
                console.print(f"  {r.task_id}: [{r.error_type}] {r.error_message or ''}")


if __name__ == "__main__":
    app()
