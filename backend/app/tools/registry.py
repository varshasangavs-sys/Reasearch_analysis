"""
The ONLY entry point agents use to talk to the tools layer.

Why a registry:
  Agents don't know which sources exist. They ask: "give me findings for this
  sub-question." Adding a 4th source = one line here, zero changes in agents.

  v2 hook (do not build): when smart routing arrives, `search_all` becomes
  `route(sub_q) -> tools_subset` and then calls the same fan-out. Signature
  stays. Callers stay. Only this file changes.

Why `asyncio.gather` is OK here even though v1 forbids parallel AGENT execution:
  This is I/O parallelism within ONE agent (the Retriever) for ONE sub-question.
  The base plan §5 explicitly allows it. What's banned is running multiple
  agents at once — that would make the state machine non-deterministic.
"""

from __future__ import annotations

import asyncio

import structlog

from app.schemas import Finding, SubQuestion
from app.tools.arxiv_tool import ArxivTool
from app.tools.base import SearchTool, dedupe
from app.tools.semantic_scholar import SemanticScholarTool
from app.tools.web import WebTool

log = structlog.get_logger()

# Instantiate once. Tools are stateless — no per-call construction cost needed.
TOOLS: list[SearchTool] = [
    WebTool(),
    SemanticScholarTool(),
    ArxivTool(),
]


async def search_all(sub_question: SubQuestion) -> list[Finding]:
    """
    Fan out to every tool, gather results, deduplicate, return.

    Per-source errors are absorbed inside `safe_search` — this function never
    raises. A run with 1 dead source returns 2 sources' worth of findings.
    """
    results = await asyncio.gather(
        *[tool.safe_search(sub_question) for tool in TOOLS],
        return_exceptions=False,  # safe_search already swallows exceptions
    )

    per_source_counts = {
        tool.source_type: (len(r.findings), r.ok)
        for tool, r in zip(TOOLS, results, strict=True)
    }
    log.info(
        "search_all_done",
        sub_question_id=sub_question.id,
        per_source=per_source_counts,
    )

    flat = [f for r in results for f in r.findings]
    return dedupe(flat)
