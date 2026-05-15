#!/usr/bin/env python3
"""Create a synthetic mini dataset for local dev when the real BrowseComp
dataset isn't available yet. Produces datasets/browsecomp/browsecomp.jsonl
with 5 representative examples."""

from __future__ import annotations

import json
from pathlib import Path

MINI_DATASET = [
    {
        "problem": "What is the ICAO airport code for the main international airport serving the capital of Iceland?",
        "answer": "BIRK",
    },
    {
        "problem": "In what year was the Eiffel Tower officially opened to the public?",
        "answer": "1889",
    },
    {
        "problem": "What programming language was created by Guido van Rossum?",
        "answer": "Python",
    },
    {
        "problem": "Which element has atomic number 79?",
        "answer": "Gold",
    },
    {
        "problem": "What is the capital city of Australia?",
        "answer": "Canberra",
    },
]

out = Path(__file__).resolve().parents[1] / "datasets" / "browsecomp" / "browsecomp.jsonl"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w") as f:
    for item in MINI_DATASET:
        f.write(json.dumps(item) + "\n")

print(f"Wrote {len(MINI_DATASET)} synthetic tasks to {out}")
print("Now run: make load-browsecomp")
