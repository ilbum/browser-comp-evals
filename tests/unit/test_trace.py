"""Unit tests for trace event construction."""

import pytest

from eval_core.trace_schema import TraceEvent
from agents.base import RunContext
from eval_core.models import TaskBudget


def test_run_context_records_events():
    ctx = RunContext(task_run_id="abc-123", budget=TaskBudget())
    ctx.record("search_query", {"query": "test"})
    ctx.record("page_opened", {"url": "https://example.com"})

    assert len(ctx.trace_events) == 2
    assert ctx.trace_events[0]["step_index"] == 0
    assert ctx.trace_events[0]["event_type"] == "search_query"
    assert ctx.trace_events[1]["step_index"] == 1
    assert ctx.trace_events[1]["event_type"] == "page_opened"


def test_trace_event_model():
    import uuid
    event = TraceEvent(
        task_run_id=uuid.uuid4(),
        step_index=7,
        event_type="search_query",
        payload={"query": "\"fourth author\" EMNLP 2021"},
    )
    assert event.step_index == 7
    assert event.event_type == "search_query"
    assert event.payload["query"] == "\"fourth author\" EMNLP 2021"


def test_trace_event_types_are_valid():
    import uuid
    valid_types = [
        "agent_thought_summary", "search_query", "search_results",
        "page_opened", "page_extracted", "candidate_answer_added",
        "candidate_answer_rejected", "verification_attempt",
        "final_answer", "tool_error",
    ]
    for et in valid_types:
        e = TraceEvent(task_run_id=uuid.uuid4(), step_index=0, event_type=et, payload={})  # type: ignore
        assert e.event_type == et
