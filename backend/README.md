# Research Copilot — Backend

A multi-agent research pipeline. Type a broad question, get a cited Markdown
report. Backed by Gemini (Flash + Pro) and three free sources: web (via
Gemini Google Search grounding), Semantic Scholar, and arXiv.

For the project overview, see [../CLAUDE.md](../CLAUDE.md).
For the file-by-file architecture, see [CLAUDE.md](CLAUDE.md).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in:

```env
GEMINI_API_KEY=<from https://aistudio.google.com/apikey>           # required
TAVILY_API_KEY=<from https://app.tavily.com>                       # optional but recommended
SEMANTIC_SCHOLAR_API_KEY=<from https://www.semanticscholar.org/product/api>  # optional
```

**Source backends:**
- **Web** → Tavily if `TAVILY_API_KEY` is set (cleanest results, 1k searches/mo free), else falls back to Gemini Google Search grounding + scrape. No config needed for fallback.
- **Semantic Scholar** → works without a key but gets throttled hard; key removes the rate limit.
- **arXiv** → no key needed.

## Run

```bash
uvicorn app.main:app --reload
```

Then either:

- **Health check** — `curl http://localhost:8000/health`
- **Research query** — `curl -N -X POST http://localhost:8000/research \
    -H "Content-Type: application/json" \
    -d '{"query":"What is mixture-of-experts in LLMs?"}'`

The `-N` disables curl's buffering so you see SSE events as they arrive.

## Test

```bash
pytest -v
```

All tests are LIVE — they hit real APIs and require `GEMINI_API_KEY` in
`.env`. Without it the suite skips itself rather than pretending to pass.

Targeted runs:

```bash
pytest tests/test_tools.py -v       # tool layer (~30s, ~3 API calls/source)
pytest tests/test_planner.py -v     # planner only (~10s)
pytest tests/test_pipeline.py -v    # full end-to-end (~90–180s, real run)
```

## Project structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app + /research SSE + /health
│   ├── config.py                # pydantic-settings, single source of truth
│   ├── schemas.py               # all Pydantic models (the contracts)
│   ├── observability.py         # structlog + emit() helper
│   ├── orchestrator.py          # the state-machine runner
│   ├── llm/
│   │   ├── client.py            # Gemini wrapper (flash/pro)
│   │   └── prompts.py           # versioned prompt constants
│   ├── tools/
│   │   ├── base.py              # SearchTool ABC + dedupe
│   │   ├── web.py               # Gemini grounding + bs4 fallback
│   │   ├── semantic_scholar.py
│   │   ├── arxiv_tool.py
│   │   └── registry.py          # search_all(sub_question)
│   └── agents/
│       ├── planner.py
│       ├── retriever.py
│       ├── critic.py
│       └── synthesizer.py
├── tests/
│   ├── conftest.py
│   ├── test_tools.py
│   ├── test_planner.py
│   └── test_pipeline.py
├── .env.example
└── pyproject.toml
```

## Phases — what's built and what's next

| Phase | Status | What |
|---|---|---|
| A | ✅ | Tools layer: web, Semantic Scholar, arXiv + registry + tests |
| B | ✅ | Planner agent |
| C | ✅ | Retriever agent |
| D | ✅ | Synthesizer agent + first end-to-end vertical slice |
| E | ✅ | Critic + bounded retry loop |
| F | ✅ | Next.js frontend with live SSE progress + cited report rendering |

v2 features (vector DB, smart routing, parallel retrieval, reliability scoring,
GraphRAG, memory) are intentionally not built — see [first_base_plan.md](../first_base_plan.md) §12.
