

# Research Copilot — Project Guide for Claude

## What this project is

A multi-agent research copilot. The user types a broad research question; the
system decomposes it, retrieves evidence from three sources (web, Semantic
Scholar, arXiv), critiques coverage, retries weak areas, and synthesizes a
cited Markdown report.

**Status:** Backend v1 + frontend v1 implemented. The full vertical slice — query in browser → live SSE progress → cited report — works end-to-end.

**Source of architectural truth:** [first_base_plan.md](first_base_plan.md).
Don't deviate from its principles (vertical builds, soft-fail tools, stateless
agents, no v2 features) without explicit user buy-in.

## Pipeline at a glance

```
Broad query
   │
   ▼
[PLANNER]      decompose into 3–6 independent sub-questions  (Flash)
   │
   ▼
[RETRIEVER]    for each sub-question, query all 3 sources,
   │           merge + dedupe + source-tag the findings
   ▼
[CRITIC]       is each sub-question adequately covered?       (Flash)
   │           gap → loop back to RETRIEVER (capped retries)
   ▼
[SYNTHESIZER]  weave tagged findings into one cited report    (Pro)
   │
   ▼
Final Markdown report with [n] citations grouped by source
```

## Layer map

| Layer | Concern | Where |
|---|---|---|
| Backend | Tools, agents, orchestrator, FastAPI SSE API | [backend/](backend/) |
| Frontend | Next.js UI with live progress + cited report rendering | [frontend/](frontend/) |

Each layer is a separate concern with a stable contract between them — that
contract is the SSE event stream from `POST /research`.

## Quick start

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows; use source .venv/bin/activate elsewhere
pip install -e ".[dev]"
# Fill GEMINI_API_KEY (required) and TAVILY_API_KEY (recommended) in .env.
# SEMANTIC_SCHOLAR_API_KEY is optional — the tool works without it but gets rate-limited.
uvicorn app.main:app --reload
```

Tests are LIVE (real APIs). Run with `pytest -v` from `backend/`.

## Pointers to deeper docs

- [backend/CLAUDE.md](backend/CLAUDE.md) — file-by-file map of the backend.
- [frontend/CLAUDE.md](frontend/CLAUDE.md) — file-by-file map of the frontend.
- [first_base_plan.md](first_base_plan.md) — the original architecture spec.

## Working conventions (apply throughout)

1. **Tools never raise.** A search source's failure becomes `ToolResult(ok=False)`.
2. **Agents are `async (state) -> state`.** State flows in, mutates, flows out.
3. **One file owns each external integration.** Gemini → `app/llm/client.py`. HTTP → inside each tool.
4. **All prompts live in `app/llm/prompts.py`** as versioned constants (`_V1`, `_V2`, …).
5. **All config in `app/config.py`.** No magic numbers or model IDs scattered.
6. **Every step emits a structured event** via `observability.emit()`. That's how the SSE stream is built and how the future dashboard will work.
7. **Build vertically.** A complete query→report path before any agent gets smart. New features that don't fit the v1 scope (vector DB, smart routing, parallel retrieval, reliability scoring) belong in v2.

## How to add things (extension hooks)

- **New search source?** Subclass `SearchTool` in `app/tools/`, register in `app/tools/registry.py:TOOLS`. No changes to agents or orchestrator.
- **New agent?** `async def agent(state) -> state`, add to `app/orchestrator.py`.
- **New event type?** Just call `emit(state, "your_event", ...)` — the SSE endpoint forwards anything in `state.events`.
- **New LLM provider?** Replace `app/llm/client.py` — nothing else imports `google.genai`.
