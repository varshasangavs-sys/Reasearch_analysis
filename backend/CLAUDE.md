# Backend — File-by-File Guide for Claude

This document is the map for future sessions. Read it before editing.

## Architectural invariants (do not violate)

1. **Tools never raise to the orchestrator.** All search tools return `ToolResult`. Failure = `ok=False`, not exceptions.
2. **Agents are `async def agent(state: ResearchState) -> ResearchState`.** This matches LangGraph's node signature; preserving it keeps the v2 LangGraph migration free.
3. **Only `app/llm/client.py` imports `google.genai`.** All other code calls `flash()` / `pro()`.
4. **All config goes through `get_settings()`.** No `os.getenv` outside `config.py`.
5. **All prompts are versioned constants in `app/llm/prompts.py`.** Bump the `_V1` → `_V2` when you change them.
6. **All pipeline observability happens via `emit(state, step, **fields)`.** That single function records to state, logs, and drives the SSE stream.

## Dependency graph (who imports whom)

```
main.py ──> orchestrator.py ──> agents/ ──> llm/, tools/, observability, schemas
                                              │
                                              ▼
                                          config.py
```

`schemas.py` and `config.py` are the spine — every other module imports from them. Keep them dependency-free in return (no agents/tools imports from these two).

## File map

### Entry points

- **`app/main.py`** — FastAPI app. Two endpoints: `POST /research` (SSE) and `GET /health`. Wires `configure_logging()` at startup via `lifespan`. Global try/except in the SSE generator turns unhandled errors into a final `error` event so the stream closes cleanly.

### Core / contracts

- **`app/config.py`** — `Settings` class (pydantic-settings) + cached `get_settings()`. The single source of truth for env vars, model IDs, retry counts, timeouts. When Gemini ships a new model, **this** is the only place that changes.

- **`app/schemas.py`** — every Pydantic model the system uses. `Source`, `Finding`, `SubQuestion`, `ResearchState`, `ToolResult`. Plus LLM-output schemas `PlannerOutput`, `CriticOutput`, `CritiqueItem`. Keep this file free of business logic — it's the contract layer.

- **`app/observability.py`** — structlog config + the `emit(state, step, **fields)` helper. `bind_run(run_id)` sets a contextvar so every log line in a run carries the same id. The `emit` function does three things at once: appends to `state.events`, logs JSON, returns the event dict for SSE.

### LLM (provider-agnostic — Strategy pattern)

The LLM layer is built so agents are blind to which model vendor is serving them. To swap providers: edit `LLM_PROVIDER` in `.env` (`gemini` or `openai`), make sure the matching `*_API_KEY` is set, restart. No agent code changes.

- **`app/llm/client.py`** — the public surface and the ROUTER. Exports `flash(prompt, schema=..., use_grounding=...)` and `pro(prompt)`. Reads `settings.LLM_PROVIDER` and dispatches to the right provider class. The provider instance is `lru_cache`'d (process-singleton), so SDK connection pools stay warm.

- **`app/llm/providers/base.py`** — `LLMProvider` ABC. Every provider implements `flash` and `pro` with the same signature. New providers (Claude, Ollama, local) inherit from this.

- **`app/llm/providers/gemini.py`** — `GeminiProvider`. The ONLY file allowed to import `google.genai`. Supports `use_grounding=True` (Google Search grounding).

- **`app/llm/providers/openai.py`** — `OpenAIProvider`. The ONLY file allowed to import `openai`. Uses `client.beta.chat.completions.parse(response_format=Model)` for structured output. `use_grounding=True` raises `NotImplementedError` — OpenAI has no built-in web search, but the web tool falls back to Tavily before reaching grounding so this never bites in practice.

- **`app/llm/prompts.py`** — all prompts as `_V1` constants. Provider-agnostic — both Gemini and OpenAI follow the same JSON-schema instruction style.

**Adding a new provider** (e.g. Claude):
1. Add `claude` to `LLM_PROVIDER`'s Literal in `config.py`.
2. Write `app/llm/providers/claude.py` with a `ClaudeProvider(LLMProvider)` class.
3. Add the dispatch branch in `client.py:_provider()`.
4. Add `ANTHROPIC_API_KEY` + model fields in `config.py`.
5. Update `missing_required()` to check the new key when `LLM_PROVIDER=claude`.

That's it. Agents, tools, orchestrator, tests — no changes.

### Tools (Phase A — the workhorse)

- **`app/tools/base.py`** — `SearchTool` ABC + `dedupe(findings)`. The ABC defines `source_type` (a `Literal["web","semantic_scholar","arxiv"]`) and `search()`. `safe_search()` is the orchestrator-facing wrapper that absorbs any escaped exception — belt-and-suspenders on top of each tool's own try/except. `dedupe` keys on normalized URL OR normalized title (handles both tracking-param dups and arXiv-vs-S2 title collisions).

- **`app/tools/web.py`** — TWO backends with automatic failover, exposed as one `WebTool`. Primary: **Tavily** (`POST https://api.tavily.com/search`) — returns clean extracted `content` per result, no scraping. Activates when `TAVILY_API_KEY` is set. Fallback: Gemini Google Search grounding + `httpx + BeautifulSoup` scrape. Strips nav/footer/script tags. Truncates to 1500 chars. Why one tool with two backends: from the system's perspective there is one "web" source — backend choice is operational, not architectural.

- **`app/tools/semantic_scholar.py`** — `GET /graph/v1/paper/search`. Sends the API key when present (raises rate limits). Skips papers without an abstract (no synthesizable content). Populates `citation_count` — seed for v2 reliability scoring.

- **`app/tools/arxiv_tool.py`** — uses the `arxiv` library. Runs the sync client in `asyncio.to_thread()` so it doesn't block the event loop. Respects `ARXIV_DELAY_SECONDS`.

- **`app/tools/registry.py`** — `TOOLS: list[SearchTool]` and `search_all(sub_q)`. Fans out with `asyncio.gather`, dedupes the merged result. **The only entry point agents use** — adding a new source = subclass + register here.

### Agents (Phase B/C/D/E)

All agents are `async def agent(state: ResearchState) -> ResearchState`.

- **`app/agents/planner.py`** — calls `flash(prompt, schema=PlannerOutput)`. On schema-parse failure, retries once with a stricter instruction. Emits `plan_ready`.

- **`app/agents/retriever.py`** — iterates `state.sub_questions`, skips already-covered ones, calls `registry.search_all(sq)`. Honors `sq.suggested_new_query` (set by Critic on retry rounds). Emits `retrieved` per sub-question.

- **`app/agents/critic.py`** — builds a digest of findings per sub-question, calls `flash(prompt, schema=CriticOutput)`. Sets `sq.covered`, `sq.suggested_new_query`, increments `sq.retry_count`. If the Critic itself fails, force-terminates by setting `retry_count = MAX_RETRIES` (prevents unbounded loops).

- **`app/agents/synthesizer.py`** — formats findings as a numbered list, calls `pro(prompt)`. Prompt explicitly forbids inventing sources. If no findings exist, emits a placeholder report instead of burning Pro tokens on an empty prompt.

### Orchestration

- **`app/orchestrator.py`** — two entry points: `run_research(query)` (returns final state) and `run_research_stream(query)` (yields events as they happen). The streaming variant drains `state.events` after each agent call. Termination: stop the retry loop when all sub-questions are covered OR every uncovered one has hit `MAX_RETRIES`. This is what makes the pipeline a state machine — and exactly the conditional-edge pattern LangGraph encodes.

### Tests (LIVE — see conftest)

- **`tests/conftest.py`** — session-level skip when `GEMINI_API_KEY` is missing. Plus reusable `SubQuestion` fixtures.

- **`tests/test_tools.py`** — each tool returns ≥1 finding for a real query; a monkeypatched-to-raise tool soft-fails; registry aggregates from ≥2 sources; `dedupe` strips tracking-param duplicates.

- **`tests/test_planner.py`** — three real queries; assert 3–6 sub-questions, no duplicates, look like research questions.

- **`tests/test_pipeline.py`** — one full end-to-end run; assert plan exists, findings cover ≥(N-1) sub-questions, report contains `[1]` and a References section, key events fired.

## Conventions & gotchas

- **Pydantic v2** is in use. Use `model_validate`, `model_dump`, not v1's `parse_obj` / `dict()`.
- **`google-genai`** package — NOT the older `google-generativeai`. The Client API is `client.aio.models.generate_content(...)` for async.
- **`asyncio.to_thread`** wraps any sync library call (currently used for `arxiv`). Don't `await` a sync function — Python won't stop you but the event loop will be blocked.
- **Citation numbering**: the Synthesizer sees findings as `[1] …`, `[2] …`. Don't reorder `state.findings` after the Synthesizer prompt is built or `[n]` references will misalign.
- **Empty abstracts** (Semantic Scholar) are skipped at the tool layer, not the agent layer — agents should never have to filter junk.

## Extension hooks (designed-for, not built)

| v2 feature | Where it slots in | Why it's painless |
|---|---|---|
| Vector DB / chunking | `app/tools/<source>.py` or a new `app/tools/chunker.py` | `Finding.content` is plain text; an `embedding` field is purely additive on the model. |
| Smart source routing | `app/tools/registry.py` | The list `TOOLS` becomes a function `tools_for(sub_q)`. `search_all` signature unchanged. |
| Parallel sub-question retrieval | `app/agents/retriever.py` | Replace the for-loop with `asyncio.gather`. State updates are append-only. |
| Reliability scoring | `app/tools/semantic_scholar.py` + scorer module | `Source.reliability_score` field already exists. `citation_count` already populated. |
| Memory / checkpointing | `app/orchestrator.py` | Add `checkpointer.save(state)` between agents. `ResearchState` is fully serializable. |
| Observability dashboard | nothing in the pipeline changes | Events are already JSON with `run_id`, `step`, `ts`. Ship them to a DB instead of stdout. |
| LangGraph migration | replace `orchestrator.py` only | Agents are LangGraph-shaped nodes already. |
