"""
Retriever agent — for each uncovered sub-question, fetch findings from all sources.

Why iterate only uncovered sub-questions:
  The Critic may mark some questions as "covered" and others not. On the next
  retrieval round, we only re-query the uncovered ones — otherwise we'd
  duplicate findings for already-good sub-questions and waste API quota.

Why "uncovered" includes the first round:
  All sub-questions start with `covered=False`. So the first pass fetches
  everything. Subsequent passes only re-fetch what the Critic rejected.
"""

from __future__ import annotations

from collections import Counter

import structlog

from app.observability import emit
from app.schemas import ResearchState
from app.tools.registry import search_all

log = structlog.get_logger()


async def retriever(state: ResearchState) -> ResearchState:
    """Append findings to state for every uncovered sub-question."""
    for sq in state.sub_questions:
        if sq.covered:
            continue

        new_findings = await search_all(sq)
        state.findings.extend(new_findings)

        per_source = Counter(f.source.type for f in new_findings)
        emit(
            state,
            "retrieved",
            sub_question_id=sq.id,
            sub_question=sq.text,
            retry_count=sq.retry_count,
            findings_count=len(new_findings),
            per_source=dict(per_source),
        )

    return state
