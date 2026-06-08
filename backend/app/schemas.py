"""
The contracts. Every other module imports from here.

Why contracts first:
  The orchestrator, agents, and tools only communicate through these shapes.
  A change to a tool's return type can never break an agent silently — Pydantic
  will reject it at the boundary. This is the same discipline that makes
  TypeScript codebases easier to refactor than untyped Python.

LangGraph mapping (for your learning):
  - `ResearchState` is the equivalent of a LangGraph `StateGraph` state schema.
  - Each agent is `async (state) -> state` — that's exactly a LangGraph node.
  - The `events` list is what LangGraph would expose via its streaming API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

SourceType = Literal["web", "semantic_scholar", "arxiv"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _short_id() -> str:
    return uuid4().hex[:8]


class Source(BaseModel):
    """
    Provenance metadata attached to every Finding at retrieval time.

    Why these fields:
      - `type` drives the citation grouping in the final report (Web / S2 / arXiv).
      - `citation_count` (S2 only) is the seed for v2 reliability scoring —
        unused today but populated so the v2 scorer has data to work with.
      - `reliability_score` is reserved for v2; sits at zero cost in v1.
    """

    type: SourceType
    title: str
    url: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    citation_count: int | None = None  # Semantic Scholar only
    reliability_score: float | None = None  # v2 placeholder, do not use in v1


class Finding(BaseModel):
    """
    One piece of evidence retrieved from one source for one sub-question.

    Why `id`:
      The Synthesizer needs a stable handle to map [1], [2], [3] citations back
      to specific findings. Without an id, dedup/reordering would break references.
    """

    id: str = Field(default_factory=_short_id)
    sub_question_id: str
    content: str  # abstract or scraped snippet, already truncated by the tool
    source: Source
    retrieved_at: datetime = Field(default_factory=_utcnow)


class SubQuestion(BaseModel):
    """
    One of the 3–6 independent questions the Planner decomposes the query into.

    Why `covered` and `retry_count` live here, not in a side dict:
      The Critic's verdict and the Retriever's retry strategy both need this
      data. Co-locating it on the sub-question keeps the state flat — easier
      to serialize for future checkpointing.

    Why `suggested_new_query`:
      When the Critic says "not covered", it must also say "try this instead."
      The Retriever consumes this field on the next round.
    """

    id: str = Field(default_factory=_short_id)
    text: str
    covered: bool = False
    retry_count: int = 0
    suggested_new_query: str | None = None


class ResearchState(BaseModel):
    """
    The shared state object that flows through the pipeline.

    Every agent receives this, mutates it (returning a new instance is fine too
    — Pydantic is cheap), and passes it on. Nothing else lives outside this
    object during a run. That's what makes the system "stateless agents over
    shared state" — exactly the LangGraph model.

    Why `run_id`:
      Every log line, every event, every future checkpoint is tagged with this.
      One run = one id. Critical for grepping logs of a specific failure.
    """

    run_id: str = Field(default_factory=lambda: uuid4().hex)
    query: str
    sub_questions: list[SubQuestion] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    report_markdown: str | None = None
    events: list[dict] = Field(default_factory=list)  # observability trace


class ToolResult(BaseModel):
    """
    The contract every search tool returns. Tools NEVER raise to the caller.

    Why this exists:
      A flaky web search must not kill the run. The orchestrator should be able
      to ask "did this source work?" without try/except clutter. `ok=False` with
      empty `findings` is the soft-fail signal.
    """

    findings: list[Finding] = Field(default_factory=list)
    ok: bool = True
    error: str | None = None


# --- LLM-output schemas (what we tell Gemini to return) ---


class PlannerOutput(BaseModel):
    """Structured output schema for the Planner LLM call."""

    sub_questions: list[str] = Field(min_length=3, max_length=6)


class CritiqueItem(BaseModel):
    """One sub-question's verdict from the Critic."""

    sub_question_id: str
    covered: bool
    reason: str
    suggested_new_query: str | None = None


class CriticOutput(BaseModel):
    """Structured output schema for the Critic LLM call."""

    critiques: list[CritiqueItem]
