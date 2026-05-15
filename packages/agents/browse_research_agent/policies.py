"""Decision policies for BrowseResearchAgentV1."""

from __future__ import annotations

from agents.browse_research_agent.state import ResearchState


def should_switch_to_verify(state: ResearchState) -> bool:
    top = state.top_candidate()
    if top is None:
        return False
    return top.support_count >= 1 and top.confidence >= 0.6


def should_finalize(state: ResearchState) -> bool:
    return state.ready_to_finalize()


def should_abandon(state: ResearchState, max_searches: int, max_pages: int) -> bool:
    return (
        len(state.searches_tried) >= max_searches
        or len(state.pages_opened) >= max_pages
    )
