"""Agent adapter protocol — the eval harness only depends on this interface."""

from __future__ import annotations

from typing import Any, Protocol

from eval_core.models import AgentResult, EvalTask, TaskBudget


class RunContext:
    """Holds runtime context injected into every agent run."""

    def __init__(
        self,
        task_run_id: str,
        budget: TaskBudget,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.task_run_id = task_run_id
        self.budget = budget
        self.config = config or {}
        self.trace_events: list[dict[str, Any]] = []

    def record(self, event_type: str, payload: dict[str, Any]) -> None:
        self.trace_events.append(
            {"step_index": len(self.trace_events), "event_type": event_type, "payload": payload}
        )


class AgentAdapter(Protocol):
    async def run_task(self, task: EvalTask, run_context: RunContext) -> AgentResult:
        ...
