"""Unit tests for web tools (extract and find_in_page — no network calls)."""

import pytest

from web_tools.extract import extract_relevant_passages, find_in_page
from web_tools.tool_models import Match


def test_find_in_page_basic():
    text = "The quick brown fox jumps over the lazy dog."
    matches = find_in_page(text, "fox")
    assert len(matches) == 1
    assert "fox" in matches[0].context.lower()


def test_find_in_page_case_insensitive():
    text = "The quick brown FOX jumps."
    matches = find_in_page(text, "fox")
    assert len(matches) == 1


def test_find_in_page_no_match():
    matches = find_in_page("hello world", "zzz")
    assert matches == []


def test_find_in_page_multiple():
    text = "cat and cat and cat"
    matches = find_in_page(text, "cat")
    assert len(matches) == 3


@pytest.mark.asyncio
async def test_extract_relevant_passages_returns_list():
    page = "Python is a great language.\n\nIt was created by Guido van Rossum.\n\nJava is also popular."
    passages = await extract_relevant_passages("Who created Python?", page)
    assert isinstance(passages, list)
    assert any("Guido" in p for p in passages)
