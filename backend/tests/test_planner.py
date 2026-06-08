"""
Live Planner tests — feed real broad queries and check the decomposition
is well-formed and non-overlapping (qualitatively).
"""

from __future__ import annotations

import pytest

from app.agents.planner import planner
from app.schemas import ResearchState

QUERIES = [
    "What is mixture-of-experts in large language models?",
    "How does retrieval-augmented generation work in production?",
    "What are the major paradigms in continual learning?",
]


@pytest.mark.parametrize("query", QUERIES)
async def test_planner_decomposes_query(query: str):
    state = ResearchState(query=query)
    state = await planner(state)

    assert 3 <= len(state.sub_questions) <= 6, (
        f"expected 3–6 sub-questions, got {len(state.sub_questions)}"
    )
    texts = [sq.text for sq in state.sub_questions]
    assert all(len(t) > 10 for t in texts), "sub-questions look too short"
    assert len(set(texts)) == len(texts), "duplicate sub-questions"
    # Every sub-question should look like a question or directive.
    assert all(any(kw in t.lower() for kw in ("what", "how", "why", "compare", "describe", "explain", "trade", "advantage", "challenge"))
               for t in texts), f"sub-questions don't look like research questions: {texts}"
