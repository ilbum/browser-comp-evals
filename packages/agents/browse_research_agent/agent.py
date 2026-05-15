"""BrowseResearchAgentV1 — the Phase 1 browsing agent."""

from __future__ import annotations

import json
import time
from typing import Any

import anthropic

from agents.base import RunContext
from agents.browse_research_agent.policies import should_abandon, should_finalize, should_switch_to_verify
from agents.browse_research_agent.prompts import (
    ANALYZE_PAGE_PROMPT,
    FINALIZE_PROMPT,
    PARSE_QUESTION_PROMPT,
    PLAN_SEARCHES_PROMPT,
    SYSTEM_PROMPT,
)
from agents.browse_research_agent.state import CandidateAnswer, RejectedCandidate, ResearchState
from eval_core.models import AgentResult, EvalTask, EvidenceItem, TaskRunStats
from web_tools.extract import extract_relevant_passages
from web_tools.fetch import open_webpage
from web_tools.search import search_web
from web_tools.tool_models import BudgetExhaustedError

_DEFAULT_MODEL = "claude-sonnet-4-6"


class BrowseResearchAgentV1:
    name = "browse-research-agent"
    version = "v1"

    def __init__(self, model: str = _DEFAULT_MODEL, api_key: str | None = None) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def run_task(self, task: EvalTask, ctx: RunContext) -> AgentResult:
        start = time.monotonic()
        state = ResearchState(question=task.question)
        stats = TaskRunStats()

        ctx.record("agent_thought_summary", {"message": "Starting research", "question": task.question})

        # Phase 1: parse clues
        state.parsed_clues = await self._parse_clues(task.question)
        ctx.record("agent_thought_summary", {"clues": state.parsed_clues})

        budget = ctx.budget

        while True:
            elapsed = time.monotonic() - start
            if elapsed > budget.max_runtime_seconds:
                stats.budget_exhausted = True
                ctx.record("tool_error", {"reason": "runtime budget exhausted"})
                break

            if stats.search_calls >= budget.max_search_calls:
                stats.budget_exhausted = True
                break

            if should_finalize(state):
                state.current_mode = "answer"
                break

            if should_abandon(state, budget.max_search_calls, budget.max_page_opens):
                stats.budget_exhausted = True
                break

            if should_switch_to_verify(state) and state.current_mode == "explore":
                state.current_mode = "verify"
                ctx.record("agent_thought_summary", {"message": "Switching to verification mode"})

            # Plan searches
            queries = await self._plan_searches(task.question, state)
            if not queries:
                break

            for query in queries[:2]:
                if stats.search_calls >= budget.max_search_calls:
                    break
                if query in state.searches_tried:
                    continue

                ctx.record("search_query", {"query": query})
                try:
                    results = await search_web(query)
                    stats.search_calls += 1
                    state.searches_tried.append(query)
                    ctx.record(
                        "search_results",
                        {"query": query, "count": len(results.results), "urls": [r.url for r in results.results]},
                    )
                except Exception as exc:
                    stats.tool_error_count += 1
                    ctx.record("tool_error", {"tool": "search_web", "error": str(exc)})
                    continue

                # Open top pages
                for sr in results.results[:3]:
                    if stats.page_opens >= budget.max_page_opens:
                        break
                    if sr.url in state.pages_opened:
                        continue

                    ctx.record("page_opened", {"url": sr.url, "title": sr.title})
                    try:
                        page = await open_webpage(sr.url)
                        stats.page_opens += 1
                        state.pages_opened.append(sr.url)
                    except Exception as exc:
                        stats.tool_error_count += 1
                        ctx.record("tool_error", {"tool": "open_webpage", "url": sr.url, "error": str(exc)})
                        continue

                    passages = await extract_relevant_passages(task.question, page.text)
                    stats.extracted_passages += len(passages)
                    ctx.record(
                        "page_extracted",
                        {"url": sr.url, "passages": passages, "content_length": page.content_length},
                    )

                    # Analyze page
                    analysis = await self._analyze_page(task.question, state, page.url, page.title, passages)
                    await self._apply_analysis(state, analysis, sr.url, ctx, stats)

        # Finalize
        stats.runtime_seconds = time.monotonic() - start
        top = state.top_candidate()

        if state.current_mode != "answer" and top and top.support_count >= 1:
            finalize_result = await self._try_finalize(task.question, state, top)
            if finalize_result.get("finalize"):
                final_answer = finalize_result.get("answer")
                ctx.record("final_answer", {"answer": final_answer, "rationale": finalize_result.get("rationale")})
                return AgentResult(
                    final_answer=final_answer,
                    confidence=top.confidence,
                    answer_rationale=finalize_result.get("rationale"),
                    evidence=[EvidenceItem(url=u) for u in top.supporting_urls],
                    stats=stats,
                )

        if top:
            ctx.record("final_answer", {"answer": top.answer, "rationale": "best available candidate"})
            return AgentResult(
                final_answer=top.answer,
                confidence=top.confidence,
                answer_rationale="best available candidate after budget exhaustion",
                evidence=[EvidenceItem(url=u) for u in top.supporting_urls],
                stats=stats,
            )

        ctx.record("final_answer", {"answer": None, "rationale": "no candidate found"})
        return AgentResult(final_answer=None, stats=stats)

    async def _parse_clues(self, question: str) -> list[str]:
        prompt = PARSE_QUESTION_PROMPT.format(question=question)
        raw = await self._complete(prompt)
        data = _safe_json(raw)
        return data.get("clues", [])

    async def _plan_searches(self, question: str, state: ResearchState) -> list[str]:
        prompt = PLAN_SEARCHES_PROMPT.format(
            question=question,
            clues=state.parsed_clues,
            searches_tried=state.searches_tried[-10:],
        )
        raw = await self._complete(prompt)
        data = _safe_json(raw)
        return data.get("queries", [])

    async def _analyze_page(
        self, question: str, state: ResearchState, url: str, title: str | None, passages: list[str]
    ) -> dict[str, Any]:
        candidates_repr = [
            {"answer": c.answer, "confidence": c.confidence} for c in state.candidate_answers
        ]
        prompt = ANALYZE_PAGE_PROMPT.format(
            question=question,
            candidates=json.dumps(candidates_repr),
            title=title or "unknown",
            url=url,
            passages="\n\n---\n\n".join(passages[:3]),
        )
        raw = await self._complete(prompt)
        return _safe_json(raw)

    async def _try_finalize(self, question: str, state: ResearchState, top: CandidateAnswer) -> dict[str, Any]:
        evidence_repr = "\n".join(f"- {u}" for u in top.supporting_urls[:5])
        prompt = FINALIZE_PROMPT.format(
            question=question,
            top_candidate=top.answer,
            evidence=evidence_repr,
        )
        raw = await self._complete(prompt)
        return _safe_json(raw)

    async def _apply_analysis(
        self,
        state: ResearchState,
        analysis: dict[str, Any],
        source_url: str,
        ctx: RunContext,
        stats: TaskRunStats,
    ) -> None:
        for nc in analysis.get("new_candidates", []):
            answer = nc.get("answer", "").strip()
            if not answer:
                continue
            existing = next((c for c in state.candidate_answers if c.answer.lower() == answer.lower()), None)
            if existing:
                existing.support_count += 1
                existing.supporting_urls.append(source_url)
                existing.confidence = max(existing.confidence, float(nc.get("confidence", 0)))
            else:
                state.candidate_answers.append(
                    CandidateAnswer(
                        answer=answer,
                        confidence=float(nc.get("confidence", 0)),
                        supporting_urls=[source_url],
                    )
                )
                stats.candidate_answers_generated += 1
                ctx.record("candidate_answer_added", {"answer": answer, "url": source_url})

        for contradiction in analysis.get("contradictions", []):
            if not contradiction:
                continue
            to_reject = next(
                (c for c in state.candidate_answers if c.answer.lower() in contradiction.lower()),
                None,
            )
            if to_reject:
                state.candidate_answers.remove(to_reject)
                state.rejected_candidates.append(
                    RejectedCandidate(answer=to_reject.answer, reason=contradiction)
                )
                ctx.record("candidate_answer_rejected", {"answer": to_reject.answer, "reason": contradiction})

    async def _complete(self, user_prompt: str) -> str:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text


def _safe_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
