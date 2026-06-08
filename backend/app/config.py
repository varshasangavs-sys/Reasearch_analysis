"""
Single source of truth for all configuration.

Why a dedicated module:
  Every external call (LLM, HTTP, retries, timeouts) reads from one place. When
  Google ships a new Gemini version, exactly one line moves. No magic numbers
  scattered through agents and tools — that's the #1 cause of "works on my
  machine" drift in agentic systems.

Loading order (pydantic-settings handles this for you):
  1. Process env vars
  2. .env file (in CWD when the app starts)
  3. Defaults defined below
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- LLM provider selection ---
    # "gemini" or "openai". Agents are provider-agnostic — they call
    # llm.flash() / llm.pro() and the router picks the right backend
    # based on this value. Change this + the matching API key, that's it.
    LLM_PROVIDER: Literal["gemini", "openai"] = "gemini"

    # --- Credentials ---
    GEMINI_API_KEY: str = Field(default="", description="Google AI Studio key (LLM_PROVIDER=gemini).")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI key (LLM_PROVIDER=openai).")
    SEMANTIC_SCHOLAR_API_KEY: str = Field(
        default="", description="Optional; raises rate limits when present."
    )
    TAVILY_API_KEY: str = Field(
        default="",
        description="Optional; primary web search backend. Falls back to Gemini grounding when empty.",
    )

    # --- Model selection (per provider) ---
    # Two tiers per provider: "fast" for logic (Planner/Retriever/Critic),
    # "synth" for the Synthesizer where output quality matters most.
    # If <PROVIDER>_SYNTH_MODEL is empty, the fast model is used for synth too.
    GEMINI_FLASH_MODEL: str = "gemini-2.5-flash"
    GEMINI_PRO_MODEL: str = "gemini-2.5-pro"
    GEMINI_SYNTH_MODEL: str = ""  # empty = use GEMINI_PRO_MODEL

    OPENAI_FAST_MODEL: str = "gpt-4o-mini"
    OPENAI_SYNTH_MODEL: str = ""  # empty = use OPENAI_FAST_MODEL; set e.g. "gpt-4o" or "gpt-5"

    # --- Pipeline knobs ---
    MAX_RETRIES: int = Field(default=2, ge=0, le=5)
    RESULTS_PER_SOURCE: int = Field(default=5, ge=1, le=20)
    REQUEST_TIMEOUT_SECONDS: float = 15.0
    ARXIV_DELAY_SECONDS: float = 3.0  # arXiv's politeness requirement

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    def missing_required(self) -> list[str]:
        """Return list of required-but-empty config keys. Used by /health and tests."""
        missing = []
        if self.LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        return missing


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached accessor. Use this everywhere instead of `Settings()` directly.
    The lru_cache makes it a singleton — env is parsed once per process.
    """
    return Settings()
