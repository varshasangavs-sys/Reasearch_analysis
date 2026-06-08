"""
Full end-to-end live pipeline test.

This is THE test that proves the whole system works. It's slow and burns
real tokens — keep it minimal but assertive.
"""

from __future__ import annotations

import pytest

from app.orchestrator import run_research


@pytest.mark.timeout(180)
async def test_end_to_end_query_to_cited_report():
    state = await run_research("What is mixture-of-experts in large language models?")

    # Planning produced sub-questions
    assert state.sub_questions, "planner did not produce any sub-questions"

    # Retrieval produced findings for at least most sub-questions
    findings_by_sq = {sq.id: 0 for sq in state.sub_questions}
    for f in state.findings:
        findings_by_sq[f.sub_question_id] = findings_by_sq.get(f.sub_question_id, 0) + 1
    sqs_with_findings = sum(1 for c in findings_by_sq.values() if c > 0)
    assert sqs_with_findings >= max(1, len(state.sub_questions) - 1), (
        f"too many sub-questions have zero findings: {findings_by_sq}"
    )

    # Report exists, has citations, has a references section
    assert state.report_markdown, "no report produced"
    md = state.report_markdown
    assert "[1]" in md, "report does not contain numbered citations"
    assert "## References" in md or "## references" in md.lower(), (
        "report is missing a References section"
    )

    # Events trace contains the major milestones
    steps = {ev["step"] for ev in state.events}
    for required in ("run_started", "plan_ready", "synthesized", "done"):
        assert required in steps, f"missing event step: {required} — got {steps}"


@pytest.mark.timeout(60)
async def test_health_reports_missing_keys(monkeypatch: pytest.MonkeyPatch):
    """Without the active provider's key, /health must report it missing."""
    from app.config import get_settings

    # Force Gemini provider with no key → GEMINI_API_KEY must be reported.
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    try:
        assert "GEMINI_API_KEY" in get_settings().missing_required()
    finally:
        get_settings.cache_clear()

    # Same shape for OpenAI provider.
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        assert "OPENAI_API_KEY" in get_settings().missing_required()
    finally:
        get_settings.cache_clear()
