"""
Structured logging + event emission.

Why this module exists, and why it's built BEFORE the agents:
  Retrofitting observability into 4 agents and 3 tools is painful. The
  `emit()` helper here does triple duty:
    1. Appends a typed event to `state.events` (so the pipeline's trace is
       reproducible from state alone — useful for replay/debugging).
    2. Emits a structured JSON log line via structlog (production debugging).
    3. Returns the event dict so the orchestrator can yield it to the SSE
       stream for the frontend.
  One helper, three uses. That's the v2 observability dashboard's seed —
  we don't have to bolt anything on later.

Why structlog instead of stdlib logging:
  Structured (JSON) fields by default. `log.info("retrieved", source="arxiv",
  count=5)` is one call that emits machine-grepable output. With stdlib you'd
  format strings and lose searchability.
"""

from __future__ import annotations

import logging
import sys
import time
from contextvars import ContextVar
from typing import Any

import structlog

from app.config import get_settings
from app.schemas import ResearchState

# A contextvar binds the current run_id across nested awaits without passing
# it explicitly. Every log line in a run carries the same id automatically.
_run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)


def _add_run_id(_logger, _method, event_dict):
    """structlog processor — injects run_id into every log line."""
    run_id = _run_id_var.get()
    if run_id is not None:
        event_dict["run_id"] = run_id
    return event_dict


def configure_logging() -> None:
    """Call once at app startup."""
    settings = get_settings()
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.LOG_LEVEL,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_run_id,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.LOG_LEVEL)
        ),
        cache_logger_on_first_use=True,
    )


def bind_run(run_id: str) -> None:
    """Bind the run_id for the current async context."""
    _run_id_var.set(run_id)


log = structlog.get_logger()


def emit(state: ResearchState, step: str, **fields: Any) -> dict:
    """
    Emit one pipeline event. Records it on the state, logs it, returns it.

    The returned dict is what the FastAPI SSE endpoint forwards to the
    frontend. Keep payloads JSON-serializable.
    """
    event = {
        "step": step,
        "ts": time.time(),
        "run_id": state.run_id,
        **fields,
    }
    state.events.append(event)
    log.info(step, **{k: v for k, v in fields.items() if _is_loggable(v)})
    return event


def _is_loggable(value: Any) -> bool:
    """Skip giant payloads from logs (still kept in state.events for replay)."""
    if isinstance(value, str) and len(value) > 500:
        return False
    if isinstance(value, list) and len(value) > 20:
        return False
    return True
