"""Unit tests for the answer grader."""

import pytest

from eval_core.grading import grade_answer


def test_exact_match():
    r = grade_answer("Canberra", "Canberra")
    assert r.is_correct is True
    assert r.score == 1.0
    assert r.strategy == "exact_normalized"


def test_case_insensitive():
    r = grade_answer("canberra", "Canberra")
    assert r.is_correct is True


def test_punctuation_stripped():
    r = grade_answer("1889.", "1889")
    assert r.is_correct is True


def test_wrong_answer():
    r = grade_answer("Sydney", "Canberra")
    assert r.is_correct is False
    assert r.score == 0.0


def test_none_prediction():
    r = grade_answer(None, "Canberra")
    assert r.is_correct is False
    assert r.predicted_normalized == ""


def test_containment_fallback():
    r = grade_answer("The answer is Canberra", "Canberra")
    assert r.is_correct is True
    assert r.strategy == "containment"


def test_article_stripped():
    r = grade_answer("the Eiffel Tower", "Eiffel Tower")
    assert r.is_correct is True


def test_alias_us():
    r = grade_answer("United States", "US")
    assert r.is_correct is True
