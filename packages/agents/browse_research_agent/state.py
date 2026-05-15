from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CandidateAnswer(BaseModel):
    answer: str
    support_count: int = 1
    supporting_urls: list[str] = []
    confidence: float = 0.0


class RejectedCandidate(BaseModel):
    answer: str
    reason: str


class ResearchState(BaseModel):
    question: str
    parsed_clues: list[str] = []
    searches_tried: list[str] = []
    pages_opened: list[str] = []
    extracted_facts: list[str] = []
    candidate_answers: list[CandidateAnswer] = []
    rejected_candidates: list[RejectedCandidate] = []
    current_mode: Literal["explore", "verify", "answer"] = "explore"

    def top_candidate(self) -> CandidateAnswer | None:
        if not self.candidate_answers:
            return None
        return max(self.candidate_answers, key=lambda c: (c.support_count, c.confidence))

    def ready_to_finalize(self) -> bool:
        top = self.top_candidate()
        if top is None:
            return False
        return top.support_count >= 2 and top.confidence >= 0.7 and not self._has_contradiction(top)

    def _has_contradiction(self, candidate: CandidateAnswer) -> bool:
        return any(
            r.answer.lower() == candidate.answer.lower() for r in self.rejected_candidates
        )
