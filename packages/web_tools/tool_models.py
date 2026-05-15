from __future__ import annotations

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str | None = None


class SearchResults(BaseModel):
    query: str
    results: list[SearchResult]


class WebPage(BaseModel):
    url: str
    final_url: str
    title: str | None = None
    text: str
    headings: list[str] = []
    content_length: int = 0
    fetch_status: int = 200


class Match(BaseModel):
    start: int
    end: int
    context: str


class BudgetExhaustedError(Exception):
    """Raised when a task run exceeds its configured tool budget."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
