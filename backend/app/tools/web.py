"""
Web search tool.

Two backends, automatic failover (no agent code knows about it):

  1. PRIMARY — Tavily (https://tavily.com). Purpose-built for AI agents:
     returns clean extracted `content` text per result, no scraping needed,
     faster and more reliable than scraping arbitrary URLs. Used when
     TAVILY_API_KEY is set.

  2. FALLBACK — Gemini Google Search grounding + BeautifulSoup scrape.
     Activates automatically when Tavily is unset OR fails. Same free quota
     as the Gemini LLM calls — no extra account.

Why one tool with two backends instead of two tools:
  From the system's perspective there is one "web" source. The choice of
  backend is an operational concern (which credentials are available, which
  is healthier right now), not an architectural one. The registry/agents
  never see this — they just call `WebTool().safe_search(sq)`.

  This mirrors the base plan §2 "primary grounding + SearXNG fallback"
  pattern, with Tavily filling the SearXNG slot.
"""

from __future__ import annotations

import asyncio

import httpx
import structlog
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.llm.client import flash
from app.schemas import Finding, Source, SubQuestion, ToolResult
from app.tools.base import SearchTool

log = structlog.get_logger()

_MAX_CONTENT_CHARS = 1500
_FETCH_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ResearchCopilot/0.1; +https://github.com/local/research-copilot)"
    )
}
_TAVILY_ENDPOINT = "https://api.tavily.com/search"


class WebTool(SearchTool):
    source_type = "web"

    async def search(self, sub_question: SubQuestion) -> ToolResult:
        settings = get_settings()
        query = sub_question.suggested_new_query or sub_question.text

        if settings.TAVILY_API_KEY:
            result = await self._tavily_search(query, sub_question)
            if result.ok and result.findings:
                return result
            log.warning(
                "tavily_failed_falling_back_to_grounding",
                error=result.error,
            )

        return await self._gemini_grounding_search(query, sub_question)

    # ------- Primary: Tavily -------

    async def _tavily_search(self, query: str, sub_question: SubQuestion) -> ToolResult:
        settings = get_settings()
        try:
            data = await _tavily_call(
                api_key=settings.TAVILY_API_KEY,
                query=query,
                max_results=settings.RESULTS_PER_SOURCE,
            )
        except Exception as e:  # noqa: BLE001
            return ToolResult(ok=False, error=f"tavily: {e}")

        results = data.get("results") or []
        if not results:
            return ToolResult(ok=False, error="tavily returned no results")

        findings: list[Finding] = []
        for r in results:
            content = (r.get("content") or "").strip()
            url = r.get("url") or ""
            title = r.get("title") or url
            if not content or not url:
                continue
            findings.append(
                Finding(
                    sub_question_id=sub_question.id,
                    content=content[:_MAX_CONTENT_CHARS],
                    source=Source(type="web", title=title, url=url),
                )
            )

        if not findings:
            return ToolResult(ok=False, error="tavily results lacked content/url")
        return ToolResult(findings=findings)

    # ------- Fallback: Gemini grounding + scrape -------

    async def _gemini_grounding_search(
        self, query: str, sub_question: SubQuestion
    ) -> ToolResult:
        settings = get_settings()

        try:
            response = await flash(
                f"Search the web and return information for: {query}",
                use_grounding=True,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("web_grounding_failed", error=str(e))
            return ToolResult(ok=False, error=f"grounding: {e}")

        chunks = _extract_grounding_chunks(response)
        if not chunks:
            return ToolResult(ok=False, error="no grounding chunks returned by Gemini")

        findings: list[Finding] = []
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers=_SCRAPE_HEADERS,
        ) as http:
            scraped = await asyncio.gather(
                *[_resolve_chunk(http, c) for c in chunks[: settings.RESULTS_PER_SOURCE]],
                return_exceptions=True,
            )

        for chunk, result in zip(chunks, scraped, strict=False):
            if isinstance(result, Exception) or not result:
                continue
            title, text = result
            findings.append(
                Finding(
                    sub_question_id=sub_question.id,
                    content=text[:_MAX_CONTENT_CHARS],
                    source=Source(
                        type="web",
                        title=title or chunk.get("title") or chunk["uri"],
                        url=chunk["uri"],
                    ),
                )
            )

        if not findings:
            return ToolResult(ok=False, error="all web fetches failed")
        return ToolResult(findings=findings)


# ---------- Tavily HTTP ----------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=8),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
async def _tavily_call(*, api_key: str, query: str, max_results: int) -> dict:
    settings = get_settings()
    body = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",  # "advanced" is slower + uses more credits
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }
    timeout = httpx.Timeout(settings.REQUEST_TIMEOUT_SECONDS, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        r = await http.post(_TAVILY_ENDPOINT, json=body)
        r.raise_for_status()
        return r.json()


# ---------- Grounding helpers (fallback path) ----------


def _extract_grounding_chunks(response) -> list[dict]:
    """Pull URL/title chunks out of a Gemini grounding response."""
    chunks: list[dict] = []
    try:
        candidates = response.candidates or []
        for cand in candidates:
            gm = getattr(cand, "grounding_metadata", None)
            if not gm:
                continue
            for c in getattr(gm, "grounding_chunks", []) or []:
                web = getattr(c, "web", None)
                if web and getattr(web, "uri", None):
                    chunks.append({"uri": web.uri, "title": getattr(web, "title", None)})
    except Exception as e:  # noqa: BLE001
        log.warning("grounding_extract_failed", error=str(e))
    return chunks


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(min=1, max=4),
    retry=retry_if_exception_type((httpx.RequestError,)),
    reraise=False,
)
async def _resolve_chunk(http: httpx.AsyncClient, chunk: dict) -> tuple[str, str] | None:
    """Fetch a chunk's URL and extract main text. Returns (title, body) or None."""
    url = chunk["uri"]
    try:
        r = await http.get(url)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        log.debug("web_fetch_failed", url=url, error=str(e))
        return None
    return _extract_text(r.text, fallback_title=chunk.get("title") or url)


def _extract_text(html: str, *, fallback_title: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "aside", "form", "noscript"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else fallback_title)
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = " ".join(main.get_text(separator=" ").split())
    return title, text
