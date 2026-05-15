"""System and turn prompts for BrowseResearchAgentV1."""

SYSTEM_PROMPT = """\
You are solving a difficult fact-finding task. The answer is a short, unique, \
verifiable fact. Your job is to research the web thoroughly and return the most \
accurate answer possible.

Rules:
- Do NOT guess or answer early.
- Prefer primary sources (official sites, papers, databases).
- Maintain a list of candidate answers and supporting evidence.
- Reject candidates when contradicted by credible evidence.
- Only finalize when you have at least two independent pieces of supporting evidence.
- When in doubt, do one more search.
"""

PARSE_QUESTION_PROMPT = """\
Question: {question}

Extract 3-5 specific clues or constraints from this question that should guide \
web searches. Think about: names, dates, locations, domain-specific terminology, \
relationships, and unique identifiers.

Return a JSON object: {{"clues": ["...", "..."]}}
"""

PLAN_SEARCHES_PROMPT = """\
Question: {question}
Clues: {clues}
Searches already tried: {searches_tried}

Propose 2-3 new, distinct search queries that have NOT been tried yet. \
Think laterally — vary the phrasing, try different angles.

Return a JSON object: {{"queries": ["...", "..."]}}
"""

ANALYZE_PAGE_PROMPT = """\
Question: {question}
Current candidates: {candidates}

Page title: {title}
Page URL: {url}

Relevant passages:
{passages}

Based on this page:
1. Are there any candidate answers for the question? If so, list them with confidence 0-1.
2. Are there any facts that contradict existing candidates?
3. What new search queries might this suggest?

Return JSON: {{
  "new_candidates": [{{"answer": "...", "confidence": 0.8, "evidence": "..."}}],
  "contradictions": ["..."],
  "suggested_queries": ["..."]
}}
"""

FINALIZE_PROMPT = """\
Question: {question}
Top candidate: {top_candidate}
Supporting evidence:
{evidence}

Is this answer confident enough to finalize? If yes, return the exact final answer.
If no, explain what additional verification is needed.

Return JSON: {{"finalize": true, "answer": "...", "rationale": "..."}}
  OR        {{"finalize": false, "reason": "..."}}
"""
