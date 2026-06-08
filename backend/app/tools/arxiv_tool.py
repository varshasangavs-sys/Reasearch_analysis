"""
arXiv tool — preprint search via the `arxiv` library.

Why the library wraps the API for us:
  Builds the OAI-style query strings, handles pagination, and respects arXiv's
  required politeness delay between requests. Hand-rolling this is a footgun.

Why `asyncio.to_thread`:
  The arxiv library is synchronous. Calling it directly inside an async tool
  would block the event loop and stall the other two sources. `to_thread`
  hands it to a thread, keeping the I/O loop responsive.
"""

from __future__ import annotations

import asyncio

import arxiv
import structlog

from app.config import get_settings
from app.schemas import Finding, Source, SubQuestion, ToolResult
from app.tools.base import SearchTool

log = structlog.get_logger()


class ArxivTool(SearchTool):
    source_type = "arxiv"

    async def search(self, sub_question: SubQuestion) -> ToolResult:
        settings = get_settings()
        query = sub_question.suggested_new_query or sub_question.text

        try:
            results = await asyncio.to_thread(_search_arxiv, query, settings.RESULTS_PER_SOURCE)
        except Exception as e:  # noqa: BLE001
            log.warning("arxiv_failed", error=str(e))
            return ToolResult(ok=False, error=str(e))

        findings: list[Finding] = []
        for r in results:
            abstract = (r.summary or "").strip()
            if not abstract:
                continue
            findings.append(
                Finding(
                    sub_question_id=sub_question.id,
                    content=abstract,
                    source=Source(
                        type="arxiv",
                        title=r.title.strip(),
                        url=r.entry_id,  # canonical arXiv URL
                        authors=[a.name for a in r.authors],
                        year=r.published.year if r.published else None,
                    ),
                )
            )

        return ToolResult(findings=findings)


def _search_arxiv(query: str, max_results: int) -> list:
    """Synchronous arxiv search, run inside `to_thread`."""
    settings = get_settings()
    client = arxiv.Client(
        page_size=max_results,
        delay_seconds=settings.ARXIV_DELAY_SECONDS,
        num_retries=2,
    )
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    return list(client.results(search))
