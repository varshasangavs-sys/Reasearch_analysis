"""
Synthesizer agent — writes the final cited Markdown report.

Why Pro (not Flash) here:
  This is the only place where output QUALITY directly determines user-visible
  quality. Pro is slower and more expensive, but worth it for one call per run.
  Everywhere else, Flash is fine.

Citation rule is enforced TWO ways:
  1. The prompt explicitly forbids inventing sources.
  2. We hand the model a numbered list — it can only cite numbers it sees.
     Any [n] referring to a number outside the list is detectable by us.

The Synthesizer never makes another network call after this — its input is
fully the contents of `state`. That makes the function deterministic given
fixed findings + model output, which makes it testable.
"""

from __future__ import annotations

import structlog

from app.llm.client import pro
from app.llm.prompts import SYNTHESIZER_PROMPT_V1
from app.observability import emit
from app.schemas import Finding, ResearchState

log = structlog.get_logger()


async def synthesizer(state: ResearchState) -> ResearchState:
    """Set `state.report_markdown` from `state.query` + `state.findings`."""
    if not state.findings:
        # Nothing to synthesize. Don't burn Pro tokens on an empty prompt.
        state.report_markdown = (
            f"# {state.query}\n\n"
            "_No findings were retrieved for this query. "
            "Try a more specific question or check that the data sources are reachable._\n"
        )
        emit(state, "synthesized_empty")
        return state

    findings_block = _format_findings(state.findings)
    prompt = SYNTHESIZER_PROMPT_V1.format(
        query=state.query,
        findings_block=findings_block,
    )

    markdown = await pro(prompt)
    state.report_markdown = markdown.strip()

    emit(
        state,
        "synthesized",
        prompt_version="v1",
        findings_used=len(state.findings),
        report_chars=len(state.report_markdown),
    )
    return state


def _format_findings(findings: list[Finding]) -> str:
    """
    Number every finding and present it as the model's source list.

    Format example:
      [1] (semantic_scholar) "Attention is All You Need" — Vaswani et al. (2017)
          URL: https://...
          Abstract: ...
    """
    lines: list[str] = []
    for i, f in enumerate(findings, 1):
        s = f.source
        meta_parts = [f"({s.type})", f'"{s.title}"']
        if s.authors:
            authors = ", ".join(s.authors[:3]) + (" et al." if len(s.authors) > 3 else "")
            meta_parts.append(f"— {authors}")
        if s.year:
            meta_parts.append(f"({s.year})")
        lines.append(f"[{i}] " + " ".join(meta_parts))
        lines.append(f"    URL: {s.url}")
        lines.append(f"    Content: {f.content}")
        lines.append("")
    return "\n".join(lines)
