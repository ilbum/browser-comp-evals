"""Deterministic answer grader for BrowseComp.

Phase 1: exact normalized match + alias expansion.
"""

from __future__ import annotations

from pydantic import BaseModel

from browsecomp.normalization import normalize_answer


class GradingResult(BaseModel):
    is_correct: bool
    score: float
    predicted_normalized: str
    expected_normalized: str
    strategy: str


def grade_answer(predicted: str | None, expected: str) -> GradingResult:
    if predicted is None:
        return GradingResult(
            is_correct=False,
            score=0.0,
            predicted_normalized="",
            expected_normalized=normalize_answer(expected),
            strategy="exact_normalized",
        )

    pred_norm = normalize_answer(predicted)
    exp_norm = normalize_answer(expected)

    is_correct = pred_norm == exp_norm

    # fallback: containment check (handles slight truncation)
    strategy = "exact_normalized"
    if not is_correct and pred_norm and exp_norm:
        if exp_norm in pred_norm or pred_norm in exp_norm:
            is_correct = True
            strategy = "containment"

    return GradingResult(
        is_correct=is_correct,
        score=1.0 if is_correct else 0.0,
        predicted_normalized=pred_norm,
        expected_normalized=exp_norm,
        strategy=strategy,
    )
