"""Unit tests for BrowseComp dataset loader."""

import json
import tempfile
from pathlib import Path

import pytest

from browsecomp.dataset_loader import load_browsecomp_tasks, sample_tasks


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_load_jsonl(tmp_path: Path):
    data = [
        {"problem": "What is 2+2?", "answer": "4"},
        {"problem": "Capital of France?", "answer": "Paris"},
    ]
    _write_jsonl(tmp_path / "browsecomp.jsonl", data)

    tasks = load_browsecomp_tasks(dataset_dir=tmp_path)
    assert len(tasks) == 2
    assert tasks[0].id == "browsecomp_0000"
    assert tasks[0].question == "What is 2+2?"
    assert tasks[0].expected_answer == "4"
    assert tasks[0].benchmark == "browsecomp"


def test_load_assigns_sequential_ids(tmp_path: Path):
    data = [{"problem": f"Q{i}", "answer": str(i)} for i in range(5)]
    _write_jsonl(tmp_path / "browsecomp.jsonl", data)
    tasks = load_browsecomp_tasks(dataset_dir=tmp_path)
    ids = [t.id for t in tasks]
    assert ids == ["browsecomp_0000", "browsecomp_0001", "browsecomp_0002", "browsecomp_0003", "browsecomp_0004"]


def test_file_not_found_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_browsecomp_tasks(dataset_dir=tmp_path)


def test_sample_by_count(tmp_path: Path):
    data = [{"problem": f"Q{i}", "answer": str(i)} for i in range(20)]
    _write_jsonl(tmp_path / "browsecomp.jsonl", data)
    tasks = load_browsecomp_tasks(dataset_dir=tmp_path)

    sampled = sample_tasks(tasks, count=5, sampling="random", seed=42)
    assert len(sampled) == 5


def test_sample_by_ids(tmp_path: Path):
    data = [{"problem": f"Q{i}", "answer": str(i)} for i in range(10)]
    _write_jsonl(tmp_path / "browsecomp.jsonl", data)
    tasks = load_browsecomp_tasks(dataset_dir=tmp_path)

    sampled = sample_tasks(tasks, task_ids=["browsecomp_0002", "browsecomp_0005"])
    assert len(sampled) == 2
    assert {t.id for t in sampled} == {"browsecomp_0002", "browsecomp_0005"}
