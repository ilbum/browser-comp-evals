from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RawBrowseCompItem(BaseModel):
    """Shape of one record from the OpenAI simple-evals BrowseComp dataset."""

    problem: str
    answer: str
    # The dataset may include extra fields; preserve them all.
    extra: dict[str, Any] = {}

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "RawBrowseCompItem":
        known = {"problem", "answer"}
        return cls(
            problem=row["problem"],
            answer=row["answer"],
            extra={k: v for k, v in row.items() if k not in known},
        )
