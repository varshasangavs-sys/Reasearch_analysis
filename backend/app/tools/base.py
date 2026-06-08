"""
Tools layer base class + shared helpers.

Why an ABC instead of a duck-typed function:
  v2 will add tools (PubMed, GitHub search, internal corpus). With an ABC,
  adding one is "subclass SearchTool, add to registry list" — no if/elif on
  source_type anywhere. The base class also locks down the never-raise contract.

Why `dedupe` lives here, not in registry.py:
  It operates purely on the Finding/Source contracts. Tools or future v2
  routing logic might want it too.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar
from urllib.parse import urlparse

import structlog

from app.schemas import Finding, SourceType, SubQuestion, ToolResult

log = structlog.get_logger()


class SearchTool(ABC):
    """Every search tool inherits from this. Each tool corresponds to ONE source."""

    source_type: ClassVar[SourceType]

    @abstractmethod
    async def search(self, sub_question: SubQuestion) -> ToolResult:
        """
        Take a sub-question, return tagged findings.

        Contract: NEVER raise. On any failure, return ToolResult(ok=False, error=...).
        The orchestrator depends on this — one dead source must not crash a run.
        """
        ...

    async def safe_search(self, sub_question: SubQuestion) -> ToolResult:
        """
        The orchestrator-facing entry point. Wraps `search` with a final
        try/except as a belt-and-suspenders measure — subclasses should already
        catch their own errors, but if one slips through, we still soft-fail.
        """
        try:
            return await self.search(sub_question)
        except Exception as e:  # noqa: BLE001 — intentional catch-all at boundary
            log.warning(
                "tool_exception_escaped",
                source=self.source_type,
                sub_question_id=sub_question.id,
                error=str(e),
            )
            return ToolResult(ok=False, error=f"{type(e).__name__}: {e}")


def _normalize_url(url: str) -> str:
    """For dedup: strip query/fragment, lowercase host."""
    try:
        p = urlparse(url)
        return f"{p.scheme.lower()}://{p.netloc.lower()}{p.path.rstrip('/')}"
    except Exception:
        return url.lower()


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


def dedupe(findings: list[Finding]) -> list[Finding]:
    """
    Drop findings with the same normalized URL OR normalized title.

    Why both keys: arXiv preprint + published Semantic Scholar paper often share
    a title but have different URLs — title catches those. Web results from
    the same article with tracking params share a URL but have varied titles —
    URL catches those.
    """
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    out: list[Finding] = []
    for f in findings:
        u = _normalize_url(f.source.url)
        t = _normalize_title(f.source.title)
        if u in seen_urls or t in seen_titles:
            continue
        seen_urls.add(u)
        seen_titles.add(t)
        out.append(f)
    return out
