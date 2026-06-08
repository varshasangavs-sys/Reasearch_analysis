"""
Critic agent — judges per-sub-question coverage; emits suggested re-queries.

THIS is what makes the system agentic: the loop. The Critic decides whether
the retrieval was good enough; if not, it tells the Retriever how to try again.

LangGraph mapping: this Critic + the orchestrator's "if all covered, break"
together form a CONDITIONAL EDGE — Critic → Retriever (loop) vs Critic →
Synthesizer (terminate). That's the canonical pattern for agentic graphs.

Termination guarantee:
  We bump `retry_count` on every uncovered verdict. The orchestrator stops
  looping when `retry_count >= MAX_RETRIES`, even if the Critic still says
  "not covered." Unbounded loops are how multi-agent systems burn money and
  hang forever — design them out at this layer.
"""

from __future__ import annotations

import structlog

from app.config import get_settings
from app.llm.client import flash
from app.llm.prompts import CRITIC_PROMPT_V1
from app.observability import emit
from app.schemas import CriticOutput, Finding, ResearchState, SubQuestion

log = structlog.get_logger()

_DIGEST_PREVIEW_CHARS = 200


async def critic(state: ResearchState) -> ResearchState:
    """For each sub-question, update `covered` / `suggested_new_query` / `retry_count`."""
    settings = get_settings()

    digest = _build_digest(state.sub_questions, state.findings)
    prompt = CRITIC_PROMPT_V1.format(digest=digest)

    try:
        result = await flash(prompt, schema=CriticOutput)
    except Exception as e:
        # If the Critic itself fails, treat all uncovered as terminally
        # uncovered (don't loop forever) and let the Synthesizer work with
        # what we have. Soft-fail philosophy applied at the agent layer.
        log.error("critic_failed", error=str(e))
        for sq in state.sub_questions:
            if not sq.covered:
                sq.retry_count = settings.MAX_RETRIES  # force termination
        emit(state, "critic_failed", error=str(e))
        return state

    assert isinstance(result, CriticOutput)
    by_id = {sq.id: sq for sq in state.sub_questions}

    for item in result.critiques:
        sq = by_id.get(item.sub_question_id)
        if sq is None or sq.covered:
            continue
        sq.covered = item.covered
        if not item.covered:
            sq.suggested_new_query = item.suggested_new_query
            sq.retry_count += 1

    emit(
        state,
        "verified",
        prompt_version="v1",
        verdicts=[
            {
                "sub_question_id": sq.id,
                "covered": sq.covered,
                "retry_count": sq.retry_count,
            }
            for sq in state.sub_questions
        ],
    )
    return state


def _build_digest(sub_questions: list[SubQuestion], findings: list[Finding]) -> str:
    """Compact view of each sub-question + its current findings for the Critic prompt."""
    lines: list[str] = []
    findings_by_sq: dict[str, list[Finding]] = {}
    for f in findings:
        findings_by_sq.setdefault(f.sub_question_id, []).append(f)

    for sq in sub_questions:
        lines.append(f"\n--- Sub-question id={sq.id} ---")
        lines.append(f"Question: {sq.text}")
        sq_findings = findings_by_sq.get(sq.id, [])
        if not sq_findings:
            lines.append("Findings: (none)")
            continue
        for i, f in enumerate(sq_findings, 1):
            preview = f.content[:_DIGEST_PREVIEW_CHARS].replace("\n", " ")
            lines.append(f"  [{i}] ({f.source.type}) {f.source.title}: {preview}…")
    return "\n".join(lines)
