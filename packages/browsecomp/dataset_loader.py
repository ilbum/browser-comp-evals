"""Load BrowseComp tasks from the OpenAI simple-evals dataset.

The dataset is expected to live at datasets/browsecomp/browsecomp.jsonl
(one JSON object per line) OR as a CSV with columns: problem, answer.

Run `python scripts/load_browsecomp.py` to populate the database.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Iterator

from browsecomp.schemas import RawBrowseCompItem
from eval_core.models import EvalTask

_DATASETS_DIR = Path(__file__).resolve().parents[2] / "datasets" / "browsecomp"


def _task_id(index: int) -> str:
    return f"browsecomp_{index:04d}"


def _iter_jsonl(path: Path) -> Iterator[dict]:
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _iter_csv(path: Path) -> Iterator[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        yield from reader


def load_browsecomp_tasks(dataset_dir: Path | None = None) -> list[EvalTask]:
    base = dataset_dir or _DATASETS_DIR

    candidates = [
        base / "browsecomp.jsonl",
        base / "browsecomp.csv",
        base / "examples.jsonl",
        base / "examples.csv",
    ]
    source = next((p for p in candidates if p.exists()), None)
    if source is None:
        raise FileNotFoundError(
            f"No BrowseComp dataset file found in {base}.\n"
            "Expected: browsecomp.jsonl or browsecomp.csv\n"
            "Download from: https://github.com/openai/simple-evals"
        )

    rows = list(_iter_jsonl(source) if source.suffix == ".jsonl" else _iter_csv(source))

    tasks: list[EvalTask] = []
    for i, row in enumerate(rows):
        item = RawBrowseCompItem.from_row(row)
        tasks.append(
            EvalTask(
                id=_task_id(i),
                benchmark="browsecomp",
                question=item.problem,
                expected_answer=item.answer,
                metadata=item.extra,
            )
        )
    return tasks


def sample_tasks(
    tasks: list[EvalTask],
    count: int | None = None,
    task_ids: list[str] | None = None,
    sampling: str = "random",
    seed: int = 42,
) -> list[EvalTask]:
    if task_ids:
        id_set = set(task_ids)
        return [t for t in tasks if t.id in id_set]

    if count is None or count >= len(tasks):
        return tasks

    if sampling == "first":
        return tasks[:count]

    import random

    rng = random.Random(seed)
    return rng.sample(tasks, count)
