from eval_core.models import EvalRunMetrics, TaskRunStats


def compute_run_metrics(stats_list: list[TaskRunStats], statuses: list[str]) -> EvalRunMetrics:
    total = len(statuses)
    completed = sum(1 for s in statuses if s in ("graded", "answered"))
    correct = sum(1 for s in stats_list if False)  # filled in by caller
    return EvalRunMetrics(
        total_tasks=total,
        completed_tasks=completed,
        correct_tasks=0,
        incorrect_tasks=0,
        timed_out_tasks=sum(1 for s in statuses if s == "timed_out"),
        failed_tasks=sum(1 for s in statuses if s == "failed"),
        accuracy=0.0,
        avg_runtime_seconds=_avg([s.runtime_seconds for s in stats_list]),
        avg_search_calls=_avg([float(s.search_calls) for s in stats_list]),
        avg_page_opens=_avg([float(s.page_opens) for s in stats_list]),
        avg_tool_errors=_avg([float(s.tool_error_count) for s in stats_list]),
    )


def compute_run_metrics_from_rows(rows: list[dict]) -> EvalRunMetrics:
    total = len(rows)
    correct = sum(1 for r in rows if r.get("is_correct"))
    timed_out = sum(1 for r in rows if r.get("status") == "timed_out")
    failed = sum(1 for r in rows if r.get("status") == "failed")
    graded = sum(1 for r in rows if r.get("status") == "graded")
    incorrect = graded - correct

    def _stat(key: str) -> list[float]:
        return [float(r.get("stats", {}).get(key, 0)) for r in rows if r.get("stats")]

    return EvalRunMetrics(
        total_tasks=total,
        completed_tasks=graded,
        correct_tasks=correct,
        incorrect_tasks=incorrect,
        timed_out_tasks=timed_out,
        failed_tasks=failed,
        accuracy=correct / graded if graded else 0.0,
        avg_runtime_seconds=_avg(_stat("runtime_seconds")),
        avg_search_calls=_avg(_stat("search_calls")),
        avg_page_opens=_avg(_stat("page_opens")),
        avg_tool_errors=_avg(_stat("tool_error_count")),
    )


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
