"""Answer string normalization for BrowseComp grading."""

from __future__ import annotations

import re
import unicodedata


_ARTICLE_RE = re.compile(r"\b(a|an|the)\b", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")

_ALIASES: dict[str, str] = {
    "united states": "us",
    "u.s.": "us",
    "u.s.a.": "us",
    "usa": "us",
    "united kingdom": "uk",
    "u.k.": "uk",
    "new york city": "nyc",
    "artificial intelligence": "ai",
}


def normalize_answer(s: str) -> str:
    """Canonical form used for exact-match grading."""
    s = unicodedata.normalize("NFKD", s)
    # strip accents
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _ARTICLE_RE.sub("", s)
    s = _WHITESPACE_RE.sub(" ", s).strip()
    # apply alias map (longest match first)
    for alias, canonical in sorted(_ALIASES.items(), key=lambda x: -len(x[0])):
        s = s.replace(alias, canonical)
    return s
