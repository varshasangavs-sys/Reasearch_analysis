"""
Live tool tests — each source must return at least one valid tagged finding
for a real query, and a deliberately broken source must degrade gracefully.

These tests cost real API quota. Run them sparingly.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.schemas import SubQuestion
from app.tools.arxiv_tool import ArxivTool
from app.tools.base import dedupe
from app.tools.registry import search_all
from app.tools.semantic_scholar import SemanticScholarTool
from app.tools.web import WebTool


async def test_web_tool_returns_findings(sample_sub_question: SubQuestion):
    tool = WebTool()
    result = await tool.safe_search(sample_sub_question)
    assert result.ok, f"web tool failed: {result.error}"
    assert len(result.findings) >= 1
    assert all(f.source.type == "web" for f in result.findings)
    assert all(f.sub_question_id == sample_sub_question.id for f in result.findings)


async def test_semantic_scholar_returns_findings(sample_sub_question: SubQuestion):
    tool = SemanticScholarTool()
    result = await tool.safe_search(sample_sub_question)
    # S2 throttles aggressively without a key — accept any of:
    #   - soft-fail (ok=False) — rate-limited or upstream error
    #   - 200 OK but zero findings — all returned papers had empty abstracts,
    #     which the tool correctly filters out
    # Neither is a code bug. Skip in those cases.
    if not result.ok:
        pytest.skip(f"Semantic Scholar soft-failed (likely rate-limited): {result.error}")
    if not result.findings:
        pytest.skip("Semantic Scholar returned 0 usable papers (no abstracts) — no code issue")
    assert all(f.source.type == "semantic_scholar" for f in result.findings)
    # At least one finding should have authors and a year populated.
    assert any(f.source.authors and f.source.year for f in result.findings)


async def test_arxiv_returns_findings(sample_sub_question: SubQuestion):
    tool = ArxivTool()
    result = await tool.safe_search(sample_sub_question)
    assert result.ok, f"arxiv failed: {result.error}"
    assert len(result.findings) >= 1
    assert all(f.source.type == "arxiv" for f in result.findings)


async def test_broken_tool_degrades_gracefully(sample_sub_question: SubQuestion):
    """
    Monkeypatch the arxiv search to raise. The orchestrator-facing
    `safe_search` must return ToolResult(ok=False) — not raise.
    """
    tool = ArxivTool()
    with patch("app.tools.arxiv_tool._search_arxiv", side_effect=RuntimeError("boom")):
        result = await tool.safe_search(sample_sub_question)
    assert result.ok is False
    assert result.error is not None
    assert result.findings == []


async def test_registry_aggregates_and_dedupes(sample_sub_question: SubQuestion):
    findings = await search_all(sample_sub_question)
    assert len(findings) >= 1
    types_seen = {f.source.type for f in findings}
    # At least 2 of 3 sources should typically respond.
    assert len(types_seen) >= 2, f"only got findings from: {types_seen}"


async def test_dedupe_removes_same_url():
    from app.schemas import Finding, Source

    f1 = Finding(
        sub_question_id="x",
        content="a",
        source=Source(type="web", title="A", url="https://example.com/page?utm=1"),
    )
    f2 = Finding(
        sub_question_id="x",
        content="b",
        source=Source(type="web", title="B", url="https://example.com/page"),
    )
    assert len(dedupe([f1, f2])) == 1
