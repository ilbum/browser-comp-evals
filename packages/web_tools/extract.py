"""Text extraction utilities for the agent research loop."""

from __future__ import annotations

import re

from web_tools.tool_models import Match


def find_in_page(page_text: str, needle: str) -> list[Match]:
    """Return context windows around every case-insensitive occurrence of needle."""
    matches: list[Match] = []
    pattern = re.compile(re.escape(needle), re.IGNORECASE)
    for m in pattern.finditer(page_text):
        start = max(0, m.start() - 150)
        end = min(len(page_text), m.end() + 150)
        matches.append(Match(start=m.start(), end=m.end(), context=page_text[start:end]))
    return matches


async def extract_relevant_passages(question: str, page_text: str) -> list[str]:
    """Extract passages likely relevant to the question.

    Heuristic approach for Phase 1: score paragraphs by keyword overlap with
    the question, return top-5.
    """
    question_words = set(re.findall(r"\w+", question.lower())) - _STOPWORDS
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", page_text) if len(p.strip()) > 80]

    def score(para: str) -> int:
        para_words = set(re.findall(r"\w+", para.lower()))
        return len(question_words & para_words)

    ranked = sorted(paragraphs, key=score, reverse=True)
    return ranked[:5]


_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "on",
    "at", "by", "for", "with", "about", "from", "this", "that", "these",
    "those", "and", "or", "but", "not", "what", "which", "who", "when",
    "where", "how", "why",
}
