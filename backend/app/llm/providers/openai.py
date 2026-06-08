"""
OpenAI implementation of LLMProvider.

This is the ONLY file in the project allowed to import `openai`.

Structured output uses the modern parse API:
  client.beta.chat.completions.parse(response_format=PydanticModel)
which is supported on gpt-4o, gpt-4o-mini, gpt-4.1, and GPT-5 family.

Grounding (in-LLM web search) is not available on OpenAI — the web tool
already falls back to Tavily when grounding fails, so this is fine.
"""

from __future__ import annotations

from typing import TypeVar

import openai
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.llm.providers.base import LLMProvider

log = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

# Retry transient transport errors. Do NOT retry RateLimitError — it's the
# OpenAI 429, retrying doesn't help, surface it to the caller fast.
_RETRYABLE = (openai.APIConnectionError, openai.APITimeoutError)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def _client(self) -> AsyncOpenAI:
        s = get_settings()
        if not s.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is empty. Set it in backend/.env, or switch "
                "LLM_PROVIDER to a backend whose key is present."
            )
        return AsyncOpenAI(api_key=s.OPENAI_API_KEY)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    async def flash(
        self,
        prompt: str,
        *,
        schema: type[T] | None = None,
        use_grounding: bool = False,
    ) -> str | T:
        if use_grounding:
            raise NotImplementedError(
                "OpenAI provider has no in-LLM grounding. The web tool's "
                "Tavily path covers web search; this branch should never be hit "
                "when LLM_PROVIDER=openai and TAVILY_API_KEY is set."
            )

        settings = get_settings()
        client = self._client()
        model = settings.OPENAI_FAST_MODEL
        messages = [{"role": "user", "content": prompt}]

        if schema is not None:
            response = await client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=schema,
            )
            parsed = response.choices[0].message.parsed
            if parsed is None:
                log.error(
                    "openai_flash_schema_parse_failed",
                    schema=schema.__name__,
                    raw=(response.choices[0].message.content or "")[:400],
                )
                raise RuntimeError(f"OpenAI returned no parsed {schema.__name__}")
            return parsed  # type: ignore[return-value]

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    async def pro(self, prompt: str) -> str:
        settings = get_settings()
        client = self._client()
        model = settings.OPENAI_SYNTH_MODEL or settings.OPENAI_FAST_MODEL
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
