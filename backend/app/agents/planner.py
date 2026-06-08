"""
Planner agent — decomposes a broad query into 3–6 independent sub-questions.

LangGraph mapping: this function IS a node. Its signature is the canonical
LangGraph node shape — `async (state) -> state`.

Why structured output instead of "parse JSON from text":
  Gemini's schema mode validates the response against a Pydantic model on
  Google's side. We never see malformed JSON if the model behaves. The fallback
  branch handles the rare case where it doesn't.
"""

from __future__ import annotations

import structlog

from app.llm.client import flash
from app.llm.prompts import PLANNER_PROMPT_V1
from app.observability import emit
from app.schemas import PlannerOutput, ResearchState, SubQuestion

log = structlog.get_logger()


async def planner(state: ResearchState) -> ResearchState:
    """Set `state.sub_questions` from `state.query`."""
    prompt = PLANNER_PROMPT_V1.format(query=state.query)

    try:
        result = await flash(prompt, schema=PlannerOutput)
    except Exception as e:
        log.error("planner_first_attempt_failed", error=str(e))
        # One retry with a stricter instruction.
        strict_prompt = (
            prompt
            + "\n\nIMPORTANT: Return ONLY a JSON object with a 'sub_questions' "
            "field containing an array of 3-6 strings. No other keys, no prose."
        )
        result = await flash(strict_prompt, schema=PlannerOutput)

    assert isinstance(result, PlannerOutput)

    state.sub_questions = [SubQuestion(text=text.strip()) for text in result.sub_questions]
    emit(
        state,
        "plan_ready",
        prompt_version="v1",
        sub_questions=[{"id": sq.id, "text": sq.text} for sq in state.sub_questions],
    )
    return state
