"""
Semantic Scholar tool — academic metadata with citation counts.

Why it's separate from arXiv:
  Different coverage (S2 indexes ~all academic publishers, not just preprints)
  and richer metadata (citation_count, which seeds v2 reliability scoring).
"""

from __future__ import annotations

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.schemas import Finding, Source, SubQuestion, ToolResult
from app.tools.base import SearchTool

log = structlog.get_logger()

_BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,abstract,authors,year,citationCount,url,externalIds"


class SemanticScholarTool(SearchTool):
    source_type = "semantic_scholar"

    async def search(self, sub_question: SubQuestion) -> ToolResult:
        settings = get_settings()

        # Skip the call entirely without a key. Anonymous traffic gets 429s
        # almost immediately, and our retry chain wastes ~7s waiting for
        # each one to fail. When the key arrives in .env, the tool wakes
        # up automatically — no other code change needed.
        if not settings.SEMANTIC_SCHOLAR_API_KEY:
            return ToolResult(
                ok=False,
                error="Semantic Scholar disabled (no SEMANTIC_SCHOLAR_API_KEY set).",
            )

        query = sub_question.suggested_new_query or sub_question.text

        try:
            papers = await _call_s2(query, settings.RESULTS_PER_SOURCE)
        except Exception as e:  # noqa: BLE001
            log.warning("s2_failed", error=str(e))
            return ToolResult(ok=False, error=str(e))

        findings: list[Finding] = []
        for p in papers:
            abstract = (p.get("abstract") or "").strip()
            if not abstract:
                continue  # No abstract = nothing to synthesize from. Skip.
            findings.append(
                Finding(
                    sub_question_id=sub_question.id,
                    content=abstract,
                    source=Source(
                        type="semantic_scholar",
                        title=p.get("title") or "(untitled)",
                        url=p.get("url") or "",
                        authors=[a.get("name", "") for a in (p.get("authors") or [])],
                        year=p.get("year"),
                        citation_count=p.get("citationCount"),
                    ),
                )
            )

        return ToolResult(findings=findings)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=8),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
async def _call_s2(query: str, limit: int) -> list[dict]:
    settings = get_settings()
    headers = {}
    if settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    params = {"query": query, "fields": _FIELDS, "limit": limit}
    timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS, connect=5.0)

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as http:
        r = await http.get(_BASE_URL, params=params)
        # 429 = rate limit. Let tenacity retry — S2 is famously aggressive
        # about throttling unauthenticated requests.
        r.raise_for_status()
        return (r.json() or {}).get("data") or []
