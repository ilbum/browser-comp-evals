"""Web search tool backed by Brave Search API.

Set BRAVE_SEARCH_API_KEY in the environment. Falls back to a mock if the key
is absent, which is useful for unit tests.
"""

from __future__ import annotations

import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from web_tools.tool_models import SearchResult, SearchResults

_BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


async def search_web(query: str, count: int = 10) -> SearchResults:
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
    if not api_key:
        return _mock_results(query)
    return await _brave_search(query, count, api_key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def _brave_search(query: str, count: int, api_key: str) -> SearchResults:
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {"q": query, "count": min(count, 20)}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(_BRAVE_ENDPOINT, headers=headers, params=params)
        resp.raise_for_status()

    data = resp.json()
    raw_results = data.get("web", {}).get("results", [])
    results = [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("url", ""),
            snippet=r.get("description"),
        )
        for r in raw_results
    ]
    return SearchResults(query=query, results=results)


def _mock_results(query: str) -> SearchResults:
    return SearchResults(
        query=query,
        results=[
            SearchResult(
                title=f"Mock result for: {query}",
                url="https://example.com/mock",
                snippet="This is a mock search result. Set BRAVE_SEARCH_API_KEY to use real search.",
            )
        ],
    )
