"""Unit tests for task budget and research state logic."""

import pytest

from agents.browse_research_agent.policies import should_abandon, should_finalize, should_switch_to_verify
from agents.browse_research_agent.state import CandidateAnswer, ResearchState


def _state_with_candidate(support: int, confidence: float) -> ResearchState:
    state = ResearchState(question="test question")
    state.candidate_answers = [
        CandidateAnswer(answer="test", support_count=support, confidence=confidence)
    ]
    return state


def test_should_not_finalize_no_candidates():
    state = ResearchState(question="q")
    assert should_finalize(state) is False


def test_should_finalize_when_strong_candidate():
    state = _state_with_candidate(support=2, confidence=0.8)
    assert should_finalize(state) is True


def test_should_not_finalize_low_support():
    state = _state_with_candidate(support=1, confidence=0.9)
    assert should_finalize(state) is False


def test_should_not_finalize_low_confidence():
    state = _state_with_candidate(support=3, confidence=0.5)
    assert should_finalize(state) is False


def test_should_switch_to_verify():
    state = _state_with_candidate(support=1, confidence=0.65)
    assert should_switch_to_verify(state) is True


def test_should_abandon_on_search_budget():
    state = ResearchState(question="q")
    state.searches_tried = [f"query_{i}" for i in range(30)]
    assert should_abandon(state, max_searches=30, max_pages=60) is True


def test_should_abandon_on_page_budget():
    state = ResearchState(question="q")
    state.pages_opened = [f"http://example.com/{i}" for i in range(60)]
    assert should_abandon(state, max_searches=30, max_pages=60) is True


def test_should_not_abandon_within_budget():
    state = ResearchState(question="q")
    state.searches_tried = ["q1", "q2"]
    state.pages_opened = ["http://a.com", "http://b.com"]
    assert should_abandon(state, max_searches=30, max_pages=60) is False
