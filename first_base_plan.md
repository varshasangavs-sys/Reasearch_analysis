# Multi-Agent Research Copilot — Engineering Plan (v1)

> **For:** Claude Code
> **From:** Solution Architecture
> **Scope of this document:** v1 = **broad-scope research only**, over **three sources** (web, Semantic Scholar, arXiv), built on **free tiers**, with a **FastAPI** backend and **Next.js** frontend. Advanced features are listed at the end as explicitly *out of scope for v1*.

---

## 0. Read this first — operating principles

1. **Build vertically, not horizontally.** Get one dumb-but-complete pipeline working end-to-end (query → cited report) before making any single agent smart. Do **not** build all four agents before any of them run.
2. **Each phase ends in a runnable demo.** Never leave the repo in a state that can't be executed and shown.
3. **Correctness before speed.** v1 is sequential. No parallelism, no caching, no vector DB until it works correctly.
4. **Every external call is wrapped, typed, and retried.** No raw API calls scattered in business logic.
5. **The agents are stateless functions over a shared state object.** State flows through the graph; agents never hold hidden state.
6. **Tag every finding with its source at the moment of retrieval.** Citations are built from these tags, not reconstructed later.
7. **Fail soft.** A dead source must degrade the result, never crash the run.

---

## 1. System overview

A broad research query enters the system and flows through a four-agent pipeline that produces a structured, cited Markdown report.

```
Broad query
   │
   ▼
[PLANNER]      decompose into 3–6 independent sub-questions
   │
   ▼
[RETRIEVER]    for each sub-question, query all 3 sources,
   │           merge + dedupe + source-tag the findings
   ▼
[CRITIC]       is each sub-question adequately covered?
   │           gap → loop back to RETRIEVER (capped retries)
   ▼
[SYNTHESIZER]  weave tagged findings into one cited report
   │
   ▼
Final Markdown report with [n] citations grouped by source
```

**v1 scope discipline (do NOT violate):**
- Abstracts / snippets only — no full-text PDF chunking, no embeddings, no vector DB.
- Sequential execution — no parallel retrieval.
- Query **all three** sources for every sub-question — no smart source routing yet.
- Single research run — no cross-session memory.

---

## 2. Technology stack (all free tier)

### LLMs (Google AI Studio — free, 1M context)
| Role | Model | Used for |
|---|---|---|
| Fast logic ("brain") | `gemini-2.5-flash` (or current Flash) | Planner, Retriever query generation, Critic |
| Synthesizer | `gemini-2.5-pro` (or current Pro) | Final report writing only |

> Configure the model IDs in **one place** (`config.py` / env). Models change; the code must not hardcode them in agents.

### Tools / data sources (all free)
| Source | Access | Notes |
|---|---|---|
| **Web search** | Gemini **Google Search Grounding** (built-in, ~free monthly quota) | Primary web layer via the SDK. |
| **Web fallback** | **SearXNG** (self-hosted, optional) | Only if grounding quota is exhausted. Defer unless needed. |
| **Page text scrape** | **BeautifulSoup4** (`bs4`) + `httpx` | Extract body text from result URLs when grounding gives links not text. |
| **Academic metadata + citations** | **Semantic Scholar API** | Free; **request a free API key** for usable rate limits. Abstracts, authors, year, citationCount, citation graph (for v2). |
| **Paper full text / preprints** | **arXiv API** | Free, no key. Use the `arxiv` Python lib. Respect ~3s politeness delay. |
| **Math/data checks** | Gemini **code execution sandbox** | Optional in v1; enable only if a sub-question needs numeric analysis. |

### Application
| Layer | Choice |
|---|---|
| Backend | **FastAPI** (async), **Pydantic v2** for all schemas |
| Streaming | **Server-Sent Events (SSE)** for live progress |
| HTTP client | **httpx** (async) |
| Frontend | **Next.js** (App Router, TypeScript) |
| Env / secrets | `pydantic-settings` + `.env` (never commit keys) |
| Logging | `structlog` (structured JSON logs — feeds the v2 observability dashboard) |

### Python deps (pin in `requirements.txt` / `pyproject.toml`)
```
fastapi, uvicorn[standard], pydantic, pydantic-settings,
httpx, beautifulsoup4, arxiv, google-genai,
structlog, tenacity, sse-starlette, python-dotenv, pytest, pytest-asyncio
```

---

## 3. Repository structure

```
research-copilot/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + /research SSE endpoint
│   │   ├── config.py               # settings (model ids, keys, limits)
│   │   ├── schemas.py              # ALL Pydantic models (state, findings, events)
│   │   ├── llm/
│   │   │   ├── client.py           # thin Gemini wrapper (flash/pro, retries)
│   │   │   └── prompts.py          # all agent prompts, versioned constants
│   │   ├── tools/
│   │   │   ├── base.py             # ToolResult type, Finding type, error contract
│   │   │   ├── web.py              # google grounding + bs4 scrape
│   │   │   ├── semantic_scholar.py
│   │   │   ├── arxiv_tool.py
│   │   │   └── registry.py         # exposes search_all(sub_question) -> [Finding]
│   │   ├── agents/
│   │   │   ├── planner.py
│   │   │   ├── retriever.py
│   │   │   ├── critic.py
│   │   │   └── synthesizer.py
│   │   ├── orchestrator.py         # the graph runner: wires agents over State
│   │   └── observability.py        # structured trace events (step, latency, tokens)
│   ├── tests/
│   │   ├── test_tools.py           # each source returns valid tagged Findings
│   │   ├── test_planner.py         # decomposition quality on fixtures
│   │   └── test_pipeline.py        # end-to-end on a canned query (mock LLM)
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # query input + run view
│   │   ├── components/
│   │   │   ├── QueryBar.tsx
│   │   │   ├── ProgressTimeline.tsx   # live SSE steps
│   │   │   ├── PlanView.tsx           # the sub-questions
│   │   │   ├── ReportView.tsx         # final markdown + citations
│   │   │   └── CitationList.tsx
│   │   └── lib/sse.ts              # SSE client hook
│   └── package.json
├── plan.md
└── README.md
```

---

## 4. Core data contracts (define in `schemas.py` FIRST)

These are the spine of the system. Build them before any agent.

```python
# Source provenance — attached at retrieval time
class Source(BaseModel):
    type: Literal["web", "semantic_scholar", "arxiv"]
    title: str
    url: str
    authors: list[str] = []
    year: int | None = None
    citation_count: int | None = None   # semantic scholar only

class Finding(BaseModel):
    sub_question_id: str
    content: str            # abstract or scraped snippet
    source: Source
    retrieved_at: datetime

class SubQuestion(BaseModel):
    id: str
    text: str
    covered: bool = False   # set by Critic
    retry_count: int = 0

class ResearchState(BaseModel):
    query: str
    sub_questions: list[SubQuestion] = []
    findings: list[Finding] = []
    report_markdown: str | None = None
    events: list[dict] = []   # trace

# Tool contract — every tool returns this, never raises to caller
class ToolResult(BaseModel):
    findings: list[Finding] = []
    ok: bool = True
    error: str | None = None
```

**Rule:** tools return `ToolResult` and **never throw** to the orchestrator. A failed source sets `ok=False` and yields zero findings; the run continues.

---

## 5. The tools layer (build + test this FIRST — Phase A)

Each tool takes a `sub_question` and returns a `ToolResult` of source-tagged `Finding`s.

### `web.py`
- Call Gemini Google Search Grounding for the sub-question.
- If grounding returns URLs without body text, fetch with `httpx` + extract with BeautifulSoup (strip nav/scripts; take main text).
- Truncate each finding's content sensibly (e.g. first ~1500 chars).
- Tag `source.type = "web"`.

### `semantic_scholar.py`
- `GET /graph/v1/paper/search` with `query`, `fields=title,abstract,authors,year,citationCount,url`, `limit=5`.
- Send the API key header if present.
- Skip papers with no abstract. Tag `source.type = "semantic_scholar"`.

### `arxiv_tool.py`
- Use the `arxiv` lib: `Search(query=..., max_results=5, sort_by=Relevance)`.
- Respect the politeness delay. Pull title, summary (abstract), authors, published year, `entry_id`/pdf url.
- Tag `source.type = "arxiv"`.

### `registry.py`
```python
async def search_all(sub_question: SubQuestion) -> list[Finding]:
    results = await asyncio.gather(   # gather is fine; this is I/O, not agent parallelism
        web.search(sub_question),
        semantic_scholar.search(sub_question),
        arxiv_tool.search(sub_question),
        return_exceptions=False,      # tools already swallow their errors
    )
    findings = [f for r in results for f in r.findings]
    return dedupe(findings)           # dedupe by normalized title + url
```

**Resilience requirements (apply to every tool):**
- Wrap network calls with `tenacity` retry: 3 attempts, exponential backoff.
- Hard timeout per call (e.g. 15s).
- On final failure: log, return `ToolResult(ok=False)`, do not raise.

**✅ Phase A done when:** `pytest test_tools.py` shows each source returning ≥1 valid `Finding` for a real query, and a deliberately-broken source degrades gracefully.

---

## 6. The agents (Phase B–E)

All prompts live in `prompts.py` as versioned constants. All agents are `async def agent(state) -> state`.

### Planner (Phase B)
- Input: `state.query`.
- Output: 3–6 `SubQuestion`s that are **non-overlapping, collectively cover the topic, and each independently answerable**.
- Use Flash with **structured JSON output** (schema-constrained). Validate against `list[SubQuestion]`; if invalid, retry once with a stricter instruction.
- **✅ Done:** run on 10 broad topics; sub-questions are clean and coverage is sensible.

### Retriever (Phase C)
- For each `SubQuestion`, call `registry.search_all()`, attach findings to state.
- No source routing — query all three. Tag everything.
- **✅ Done:** every sub-question has source-tagged findings from multiple sources.

### Synthesizer (Phase D)
- Input: query + all findings.
- Output: structured Markdown report — one section per sub-question + intro + conclusion.
- **Citation rule:** every non-trivial claim ends with `[n]`, where `n` maps to a numbered source in a references list. The model must only cite from provided findings — never invent sources. Pass findings with stable numeric ids and instruct strict grounding.
- Use **Pro** here (quality matters).
- **✅ Done:** end-to-end pipeline (Planner→Retriever→Synthesizer) yields a coherent cited report. **This is the first full vertical slice.**

### Critic + loop (Phase E) — this makes it *agentic*
- After retrieval, Critic (Flash) judges per sub-question: *Is there enough grounded material to answer this?* Output: `{sub_question_id, covered: bool, reason, suggested_new_query?}`.
- If `covered=false` and `retry_count < MAX_RETRIES (2)`: re-run Retriever for that sub-question using `suggested_new_query`; increment `retry_count`.
- **Termination:** stop when all covered OR every uncovered sub-question hit max retries. Never loop unbounded.
- **✅ Done:** feed a hard query whose first search is weak; observe a re-search triggered and resolved (or gracefully abandoned).

---

## 7. Orchestrator (`orchestrator.py`)

A simple explicit state-machine runner (no heavy framework needed for v1; keep it transparent):

```python
async def run_research(query: str, emit) -> ResearchState:
    state = ResearchState(query=query)
    emit("planning")
    state = await planner(state)
    emit("plan_ready", plan=state.sub_questions)

    for round in range(MAX_RETRIES + 1):
        emit("retrieving", round=round)
        state = await retriever(state)        # only fills uncovered sub-qs
        emit("verifying")
        state = await critic(state)
        if all(sq.covered for sq in state.sub_questions):
            break

    emit("synthesizing")
    state = await synthesizer(state)
    emit("done")
    return state
```

`emit` pushes a structured event to both the SSE stream and `observability.py`.

---

## 8. API (`main.py`)

- `POST /research` — body `{ "query": str }`. Returns an **SSE stream** of events:
  - `planning` → `plan_ready{sub_questions}` → `retrieving{round}` → `verifying` → (loop) → `synthesizing` → `report{markdown, citations}` → `done`
  - plus `error{message}` events that never tear down the stream uncleanly.
- `GET /health` — readiness check (verifies keys present).
- CORS configured for the Next.js origin.
- Use `sse-starlette`'s `EventSourceResponse`.

---

## 9. Frontend (Next.js) — Phase F

**Design direction (per design principles): editorial / "research desk" aesthetic — calm, typographic, paper-like, NOT a generic purple-gradient SaaS dashboard.**

- **Typography:** a distinctive serif display face for headings (e.g. a Fraunces/Newsreader-style serif) paired with a clean grotesque for body. Avoid Inter/Roboto/Arial.
- **Palette:** warm off-white "paper" background, ink-black text, a single sharp accent (e.g. a deep archival red or ink-blue) for citations and active states. Dark mode optional.
- **Layout:** generous margins, a single reading column for the report (max ~70ch), a left rail for the live progress timeline. Asymmetric, document-like.
- **Motion:** restrained. Staggered reveal of sub-questions as the plan arrives; a quiet pulse on the active pipeline step. No gratuitous animation.

**Components:**
1. `QueryBar` — large, inviting text input; submit triggers the SSE connection.
2. `ProgressTimeline` — renders pipeline steps live from SSE: Planning → Retrieving (round n) → Verifying → Synthesizing → Done. Active step highlighted.
3. `PlanView` — shows the sub-questions as they're decided (proves the system *plans*).
4. `ReportView` — renders the final Markdown; inline `[n]` citations are clickable, scrolling to references.
5. `CitationList` — references grouped by source type (Web / Semantic Scholar / arXiv) with links, authors, year.

**`lib/sse.ts`** — a typed hook consuming the event stream and updating React state per event type.

**✅ Phase F done:** type a broad query in the browser, watch the plan appear, watch the pipeline progress live, read a cited report with working citation links.

---

## 10. Build order (the contract)

| Phase | Deliverable | Done when |
|---|---|---|
| **A** | Tools layer + tests | each source returns valid tagged Findings; broken source degrades gracefully |
| **B** | Planner | clean 3–6 sub-questions on 10 topics |
| **C** | Retriever | every sub-question has multi-source tagged findings |
| **D** | Synthesizer | full pipeline → coherent cited report (first vertical slice) |
| **E** | Critic + loop | weak first search triggers a bounded re-search |
| **F** | FastAPI SSE + Next.js UI | browser: query → live progress → cited report |

Commit after each phase. Write one README paragraph per phase: what it does + what you learned.

---

## 11. Cross-cutting requirements (apply throughout)

- **Config in one place.** Model ids, API keys, `MAX_RETRIES`, `RESULTS_PER_SOURCE`, timeouts — all in `config.py` via env. No magic numbers in agents.
- **Resilience.** Every external call: timeout + `tenacity` retry + soft-fail. The fallback chain (grounding → SearXNG) is a v2 hook but design the web tool so it can be swapped.
- **Observability from day one.** Every `emit` writes a structured event (step, duration_ms, model, token_usage if available). This is the seed of the v2 dashboard — don't bolt it on later.
- **No secrets in code or git.** `.env` only; provide `.env.example`.
- **Type everything.** Pydantic on the boundary, type hints throughout. Tools never return loose dicts.
- **Tests are part of "done."** Tools and Planner have tests; pipeline has one mock-LLM end-to-end test.
- **Grounded generation is non-negotiable.** Synthesizer cites only provided findings; never fabricates sources. If a claim has no finding, it must be hedged or dropped.

---

## 12. Explicitly OUT OF SCOPE for v1 (do not build yet)

These are v2+. Designed-for, not built:
- Full-text PDF ingestion, chunking, embeddings, **vector DB** (RAG layer).
- **Smart source routing** (Retriever choosing sources by sub-question type).
- **Parallel** sub-question retrieval (true agent concurrency).
- **Source reliability scoring** / weighting.
- **GraphRAG** / citation-graph traversal.
- **Memory** (cross-session episodic reuse of past research).
- **Voice** interface.
- **Observability dashboard** UI (we collect the events in v1; visualize in v2).
- Multi-query expansion per sub-question.

Keep interfaces clean enough that each of these slots in without a rewrite (e.g. `registry.search_all` can later become routing-aware; `Finding.source` already carries the metadata reliability scoring will need).

---

## 13. First task for Claude Code

Start with **Phase A**, in this order:
1. Scaffold `backend/` with `config.py`, `schemas.py` (all contracts from §4), and `.env.example`.
2. Implement the three tools (`web.py`, `semantic_scholar.py`, `arxiv_tool.py`) and `registry.search_all`.
3. Write `tests/test_tools.py` proving real findings come back and failures degrade gracefully.
4. Stop and show the test output before moving to the Planner.

Do not scaffold the frontend or the agents until the tools layer is green.