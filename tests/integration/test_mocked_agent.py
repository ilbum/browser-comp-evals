"""Integration test: run a task end-to-end with a mocked agent."""

from __future__ import annotations

import uuid

import pytest

from agents.base import AgentAdapter, RunContext
from eval_core.grading import grade_answer
from eval_core.models import AgentResult, EvalTask, TaskBudget, TaskRunStats


class MockCorrectAgent:
    """Always returns the expected answer."""

    async def run_task(self, task: EvalTask, ctx: RunContext) -> AgentResult:
        ctx.record("search_query", {"query": "mock search"})
        ctx.record("final_answer", {"answer": task.expected_answer})
        return AgentResult(
            final_answer=task.expected_answer,
            confidence=1.0,
            stats=TaskRunStats(search_calls=1, page_opens=1, runtime_seconds=0.1),
        )


class MockWrongAgent:
    """Always returns a wrong answer."""

    async def run_task(self, task: EvalTask, ctx: RunContext) -> AgentResult:
        ctx.record("final_answer", {"answer": "WRONG_ANSWER"})
        return AgentResult(
            final_answer="WRONG_ANSWER",
            confidence=0.1,
            stats=TaskRunStats(runtime_seconds=0.1),
        )


class MockBudgetExhaustedAgent:
    """Exhausts budget without finding answer."""

    async def run_task(self, task: EvalTask, ctx: RunContext) -> AgentResult:
        ctx.record("tool_error", {"reason": "budget exhausted"})
        return AgentResult(
            final_answer=None,
            stats=TaskRunStats(budget_exhausted=True, runtime_seconds=600.0),
        )


@pytest.mark.asyncio
async def test_correct_agent_grades_correctly():
    task = EvalTask(
        id="test_0001",
        benchmark="browsecomp",
        question="What is the capital of France?",
        expected_answer="Paris",
    )
    ctx = RunContext(task_run_id=str(uuid.uuid4()), budget=TaskBudget())
    agent = MockCorrectAgent()
    result = await agent.run_task(task, ctx)

    grading = grade_answer(result.final_answer, task.expected_answer)
    assert grading.is_correct is True
    assert grading.score == 1.0
    assert len(ctx.trace_events) == 2
    assert ctx.trace_events[-1]["event_type"] == "final_answer"


@pytest.mark.asyncio
async def test_wrong_agent_grades_incorrectly():
    task = EvalTask(
        id="test_0002",
        benchmark="browsecomp",
        question="What is the capital of France?",
        expected_answer="Paris",
    )
    ctx = RunContext(task_run_id=str(uuid.uuid4()), budget=TaskBudget())
    agent = MockWrongAgent()
    result = await agent.run_task(task, ctx)

    grading = grade_answer(result.final_answer, task.expected_answer)
    assert grading.is_correct is False
    assert grading.score == 0.0


@pytest.mark.asyncio
async def test_budget_exhausted_agent_returns_none():
    task = EvalTask(
        id="test_0003",
        benchmark="browsecomp",
        question="Some impossible question",
        expected_answer="unknown",
    )
    ctx = RunContext(task_run_id=str(uuid.uuid4()), budget=TaskBudget())
    agent = MockBudgetExhaustedAgent()
    result = await agent.run_task(task, ctx)

    assert result.final_answer is None
    assert result.stats.budget_exhausted is True
    grading = grade_answer(result.final_answer, task.expected_answer)
    assert grading.is_correct is False


@pytest.mark.asyncio
async def test_agent_adapter_protocol_satisfied():
    """Verify MockCorrectAgent satisfies AgentAdapter structural protocol."""
    task = EvalTask(
        id="test_0004",
        benchmark="browsecomp",
        question="test",
        expected_answer="test",
    )
    ctx = RunContext(task_run_id=str(uuid.uuid4()), budget=TaskBudget())
    agent: AgentAdapter = MockCorrectAgent()  # type: ignore
    result = await agent.run_task(task, ctx)
    assert result is not None
