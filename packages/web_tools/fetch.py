"""Fetch and clean web pages."""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from web_tools.tool_models import WebPage

_MAX_TEXT_CHARS = 50_000
_SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "form"}


async def open_webpage(url: str) -> WebPage:
    return await _fetch_and_parse(url)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def _fetch_and_parse(url: str) -> WebPage:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; BrowseCompEvalBot/1.0; +https://github.com/browsecomp)"
        )
    }
    async with httpx.AsyncClient(
        timeout=20.0, follow_redirects=True, headers=headers
    ) as client:
        resp = await client.get(url)

    final_url = str(resp.url)
    soup = BeautifulSoup(resp.text, "lxml")

    for tag in soup(list(_SKIP_TAGS)):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else None

    headings = [
        h.get_text(strip=True)
        for h in soup.find_all(["h1", "h2", "h3"])
        if h.get_text(strip=True)
    ][:20]

    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    text = text[:_MAX_TEXT_CHARS]

    return WebPage(
        url=url,
        final_url=final_url,
        title=title,
        text=text,
        headings=headings,
        content_length=len(text),
        fetch_status=resp.status_code,
    )
