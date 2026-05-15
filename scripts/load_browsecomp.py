#!/usr/bin/env python3
"""Seed the eval_tasks table with BrowseComp tasks.

Usage:
    python scripts/load_browsecomp.py
    make load-browsecomp
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))

from sqlalchemy import select, text

from api.db.session import AsyncSessionLocal
from api.db.models import EvalTaskRow
from browsecomp.dataset_loader import load_browsecomp_tasks


async def main() -> None:
    print("Loading BrowseComp tasks from dataset files...")
    try:
        tasks = load_browsecomp_tasks()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(tasks)} tasks. Inserting into database...")

    inserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        existing_ids: set[str] = set(
            (await session.execute(select(EvalTaskRow.id))).scalars().all()
        )

        for task in tasks:
            if task.id in existing_ids:
                skipped += 1
                continue
            session.add(
                EvalTaskRow(
                    id=task.id,
                    benchmark=task.benchmark,
                    question=task.question,
                    expected_answer=task.expected_answer,
                    metadata_=task.metadata,
                )
            )
            inserted += 1

        await session.commit()

    print(f"\nLoaded {len(tasks)} BrowseComp tasks")
    print(f"Inserted: {inserted}")
    print(f"Skipped:  {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
