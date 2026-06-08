"""
Gemini implementation of LLMProvider.

This is the ONLY file in the project allowed to import google.genai.
Everything else goes through the LLMProvider interface.

Free-tier note: Gemini's free tier currently grants 0 Pro requests per day
and 20 Flash requests per day. If you're hitting RESOURCE_EXHAUSTED, either
enable billing on your Google Cloud project OR switch LLM_PROVIDER to a
different backend in .env.
"""

from __future__ import annotations

from typing import TypeVar

import structlog
from google import genai
from google.genai import types
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

# Retry transient network/timeout errors. Do NOT retry quota errors (429
# RESOURCE_EXHAUSTED) — retrying won't help and will just delay the failure.
_RETRYABLE = (ConnectionError, TimeoutError)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def _client(self) -> genai.Client:
        s = get_settings()
        if not s.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is empty. Set it in backend/.env, or switch "
                "LLM_PROVIDER to a backend whose key is present."
            )
        return genai.Client(api_key=s.GEMINI_API_KEY)

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
        if schema and use_grounding:
            raise ValueError("schema and use_grounding cannot both be set")

        settings = get_settings()
        client = self._client()

        config_kwargs: dict = {}
        if schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = schema
        if use_grounding:
            config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        response = await client.aio.models.generate_content(
            model=settings.GEMINI_FLASH_MODEL,
            contents=prompt,
            config=config,
        )

        if schema is not None:
            parsed = response.parsed
            if parsed is None:
                try:
                    parsed = schema.model_validate_json(response.text or "")
                except Exception as e:
                    log.error(
                        "gemini_flash_schema_parse_failed",
                        schema=schema.__name__,
                        raw=(response.text or "")[:400],
                        error=str(e),
                    )
                    raise
            return parsed  # type: ignore[return-value]

        if use_grounding:
            return response  # type: ignore[return-value]

        return response.text or ""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    async def pro(self, prompt: str) -> str:
        settings = get_settings()
        client = self._client()
        model = settings.GEMINI_SYNTH_MODEL or settings.GEMINI_PRO_MODEL
        response = await client.aio.models.generate_content(
            model=model,
            contents=prompt,
        )
        return response.text or ""
