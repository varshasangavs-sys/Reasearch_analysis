"""
Shared pytest fixtures + the global skip rule.

Why the env check is a session-level skip:
  All tests in this suite are LIVE — they hit real APIs. Without
  GEMINI_API_KEY they cannot run. We refuse to run them silently rather than
  pretend a missing-key state is "passing." That's how you ship broken code
  to prod thinking your CI is green.

Why we check via `get_settings()` instead of `os.getenv`:
  pytest doesn't auto-load `.env`. pydantic-settings reads `.env` only when
  `Settings()` is instantiated, and the values land on the Settings instance,
  NOT in os.environ. Going through `get_settings()` uses the same loading
  path as the app itself — single source of truth for "is config valid?".
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.schemas import SubQuestion


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    """Skip the entire suite when required env vars are absent.

    Provider-aware: only the *active* LLM_PROVIDER's API key is required.
    Going through settings.missing_required() means the test suite uses the
    same definition of "valid config" that /health and the orchestrator use.
    """
    missing = get_settings().missing_required()
    if missing:
        skip = pytest.mark.skip(reason=f"Required env vars not set: {missing}")
        for item in items:
            item.add_marker(skip)


@pytest.fixture
def sample_sub_question() -> SubQuestion:
    return SubQuestion(text="What is the transformer attention mechanism in deep learning?")


@pytest.fixture
def hard_sub_question() -> SubQuestion:
    """A sub-question that some sources may not have great answers for —
    useful for exercising the Critic retry loop."""
    return SubQuestion(text="Practical engineering trade-offs of mixture-of-experts routing.")
