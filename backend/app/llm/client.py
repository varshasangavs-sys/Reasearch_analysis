"""
Public LLM surface. Agents import `flash` / `pro` from here.

This file is now a thin ROUTER, not the implementation. It reads
`LLM_PROVIDER` from settings and dispatches to the concrete provider class
(GeminiProvider or OpenAIProvider). Adding Claude/Ollama later is a 3-line
change here + one new file under `providers/`.

Why provider selection is cached:
  Providers hold an API client. Building it on every call would defeat the
  SDK's connection pooling. lru_cache makes it a process-singleton; flipping
  LLM_PROVIDER in .env requires a restart (which is correct — we don't want
  config flips mid-run).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from app.config import get_settings
from app.llm.providers.base import LLMProvider

T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=1)
def _provider() -> LLMProvider:
    """Pick the active provider based on settings.LLM_PROVIDER."""
    s = get_settings()
    if s.LLM_PROVIDER == "gemini":
        from app.llm.providers.gemini import GeminiProvider

        return GeminiProvider()
    if s.LLM_PROVIDER == "openai":
        from app.llm.providers.openai import OpenAIProvider

        return OpenAIProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {s.LLM_PROVIDER!r}")


async def flash(
    prompt: str,
    *,
    schema: type[T] | None = None,
    use_grounding: bool = False,
) -> str | T:
    """Fast/cheap model call. See LLMProvider.flash for kwargs."""
    return await _provider().flash(prompt, schema=schema, use_grounding=use_grounding)


async def pro(prompt: str) -> str:
    """High-quality synthesis call."""
    return await _provider().pro(prompt)
