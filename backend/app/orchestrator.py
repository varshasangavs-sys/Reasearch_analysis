"""
The state machine that wires the four agents together.

What this is in LangGraph terms:
  - Nodes: planner, retriever, critic, synthesizer
  - State: ResearchState (Pydantic model)
  - Edges: linear START -> planner -> retriever -> critic
  - Conditional edge: critic -> retriever (if uncovered & retry budget left)
                      critic -> synthesizer (otherwise)
  - Edge: synthesizer -> END

We wrote it as an explicit loop instead of using LangGraph because for 4
nodes and one conditional edge, the framework's mechanics would obscure
your learning. Once you understand this loop, swapping in LangGraph gives
you checkpointing and visualization for free — but only AFTER the simple
version makes sense.

Two public functions:
  - `run_research(query)`: returns the final state (used by tests).
  - `run_research_stream(query)`: yields events one by one (used by SSE).

Streaming pattern:
  Agents are NOT generators — they just call `emit(state, ...)` to append to
  `state.events`. After each agent runs, the streaming orchestrator drains
  any new events from `state.events` and yields them. This keeps agent code
  free of streaming concerns (single responsibility).
"""

from __future__ import annotations

from typing import AsyncIterator

import structlog

from app.agents.critic import critic
from app.agents.planner import planner
from app.agents.retriever import retriever
from app.agents.synthesizer import synthesizer
from app.config import get_settings
from app.observability import bind_run, emit
from app.schemas import ResearchState

log = structlog.get_logger()


async def run_research(query: str) -> ResearchState:
    """
    Execute the full pipeline and return the final state.

    Use this when you don't need streaming (tests, CLI scripts, batch jobs).
    """
    state = ResearchState(query=query)
    bind_run(state.run_id)
    emit(state, "run_started", query=query)

    await _run_pipeline(state)
    emit(state, "done")
    return state


async def run_research_stream(query: str) -> AsyncIterator[dict]:
    """
    Execute the pipeline and yield each event as it happens.

    This is what the FastAPI SSE endpoint consumes. Each yielded dict is one
    Server-Sent Event payload. The frontend renders progress live from these.
    """
    state = ResearchState(query=query)
    bind_run(state.run_id)
    settings = get_settings()

    last_yielded = 0

    def new_events() -> list[dict]:
        """Return events appended since the last drain, and advance the cursor."""
        nonlocal last_yielded
        events = state.events[last_yielded:]
        last_yielded = len(state.events)
        return events

    emit(state, "run_started", query=query)
    for ev in new_events():
        yield ev

    await planner(state)
    for ev in new_events():
        yield ev

    for round_num in range(settings.MAX_RETRIES + 1):
        emit(state, "retrieving", round=round_num)
        for ev in new_events():
            yield ev

        await retriever(state)
        for ev in new_events():
            yield ev

        emit(state, "verifying", round=round_num)
        for ev in new_events():
            yield ev

        await critic(state)
        for ev in new_events():
            yield ev

        if all(sq.covered for sq in state.sub_questions):
            break
        # Termination guard: if every uncovered sub-question has hit its
        # retry budget, no further rounds will help. Break out and synthesize.
        if all(
            sq.covered or sq.retry_count >= settings.MAX_RETRIES
            for sq in state.sub_questions
        ):
            break

    emit(state, "synthesizing")
    for ev in new_events():
        yield ev

    await synthesizer(state)
    for ev in new_events():
        yield ev

    # The Synthesizer numbers findings [1]..[n] in the order they appear in
    # state.findings. Sending the structured list with the report lets the
    # frontend render a proper bibliography without regex-parsing the markdown.
    emit(
        state,
        "report",
        report=state.report_markdown,
        findings=[f.model_dump(mode="json") for f in state.findings],
    )
    emit(state, "done")
    for ev in new_events():
        yield ev


async def _run_pipeline(state: ResearchState) -> None:
    """Non-streaming pipeline body — shared logic for `run_research`."""
    settings = get_settings()

    await planner(state)

    for round_num in range(settings.MAX_RETRIES + 1):
        emit(state, "retrieving", round=round_num)
        await retriever(state)
        emit(state, "verifying", round=round_num)
        await critic(state)

        if all(sq.covered for sq in state.sub_questions):
            break
        if all(
            sq.covered or sq.retry_count >= settings.MAX_RETRIES
            for sq in state.sub_questions
        ):
            break

    emit(state, "synthesizing")
    await synthesizer(state)
