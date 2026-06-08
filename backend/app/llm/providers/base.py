"""
LLMProvider — the abstract contract every provider implements.

Why an ABC:
  Agents call `llm.flash()` / `llm.pro()` from one router module. The router
  dispatches to whichever concrete provider is active. Adding GPT/Claude/Ollama
  later means writing one more file in this folder and registering it in
  client.py — no agent change.

Two methods, two roles:
  - flash(): fast/cheap logic — Planner, Retriever, Critic.
    Optionally takes a Pydantic schema for structured JSON output, or
    use_grounding=True for in-LLM web search (Gemini-only feature; other
    providers raise NotImplementedError and the web tool falls back to Tavily).
  - pro(): the higher-quality model for the Synthesizer.

We deliberately keep the surface tiny. The temptation is to expose temperature,
top_p, max_tokens, etc. — resist it. If you need those knobs, push them into
the provider's __init__ from settings; don't leak them into the agent layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Common interface for all LLM backends. Agents talk to this shape."""

    name: str  # short identifier used in logs/observability

    @abstractmethod
    async def flash(
        self,
        prompt: str,
        *,
        schema: type[T] | None = None,
        use_grounding: bool = False,
    ) -> str | T:
        """
        Call the fast model.

        - schema=SomeModel → returns parsed SomeModel instance (structured JSON).
        - use_grounding=True → enables provider-native web grounding.
          May raise NotImplementedError on providers that don't support it.
        - default → returns raw text.
        """
        ...

    @abstractmethod
    async def pro(self, prompt: str) -> str:
        """Call the higher-quality synthesis model. Always returns plain text."""
        ...
