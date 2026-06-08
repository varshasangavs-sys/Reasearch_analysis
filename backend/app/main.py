"""
FastAPI app — HTTP + SSE entry points.

Endpoints:
  POST /research  — accepts a query, returns Server-Sent Events as the
                    pipeline runs. Frontend renders progress live from this.
  GET  /health    — readiness check. Reports any missing required config so
                    Ops/CI can tell broken deploys from healthy ones quickly.

CORS:
  Permitted for http://localhost:3000 (the future Next.js dev server). Add more
  origins via env when you deploy.

Why a global exception handler that emits an SSE `error` event:
  SSE streams that close uncleanly leave the browser hanging without feedback.
  By converting unhandled errors to a final event the frontend can render
  ("something went wrong"), we keep the UX honest under failure.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.observability import configure_logging, log
from app.orchestrator import run_research_stream


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Modern FastAPI startup hook (replaces the deprecated @app.on_event).
    configure_logging()
    log.info("backend_started", missing=get_settings().missing_required())
    yield


app = FastAPI(title="Research Copilot — Backend", version="0.1.0", lifespan=lifespan)


# CORS — broad in dev, lock down per-origin in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)


@app.get("/health")
async def health() -> dict:
    """Cheap readiness probe. Reports missing required env vars."""
    settings = get_settings()
    missing = settings.missing_required()
    return {"ok": not missing, "missing": missing}


@app.post("/research")
async def research(req: ResearchRequest) -> EventSourceResponse:
    """
    Run the research pipeline; stream events as SSE.

    Each event is emitted as `data: {json}\\n\\n` on the wire. The `step`
    field is what the frontend switches on:
      run_started | plan_ready | retrieving | retrieved | verifying |
      verified | synthesizing | synthesized | report | done | error
    """

    async def event_generator():
        try:
            async for event in run_research_stream(req.query):
                yield {"event": event["step"], "data": json.dumps(event, default=str)}
        except Exception as e:  # noqa: BLE001
            log.exception("research_pipeline_crashed")
            yield {
                "event": "error",
                "data": json.dumps({"step": "error", "message": str(e)}),
            }

    return EventSourceResponse(event_generator())
