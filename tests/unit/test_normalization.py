"""Unit tests for answer normalization."""

import pytest

from browsecomp.normalization import normalize_answer


def test_lowercase():
    assert normalize_answer("HELLO") == "hello"


def test_strip_punctuation():
    assert normalize_answer("hello, world!") == "hello  world"


def test_strip_accents():
    assert normalize_answer("café") == "cafe"


def test_collapse_whitespace():
    assert normalize_answer("  hello   world  ") == "hello world"


def test_article_removal():
    assert normalize_answer("the quick brown fox") == "quick brown fox"
    assert normalize_answer("a quick fox") == "quick fox"


def test_alias_united_states():
    assert normalize_answer("United States") == "us"
    assert normalize_answer("U.S.A.") == "us"


def test_alias_uk():
    assert normalize_answer("United Kingdom") == "uk"


def test_empty_string():
    assert normalize_answer("") == ""
