"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

from src.common.config import get_settings
from src.observability.langfuse_client import get_langfuse_client

TEST_LOCAL_ENV_KEYS = (
    "BRAIN_DEFAULT_MODEL",
    "BRAIN_DEFAULT_LAYER",
    "BRAIN_LOG_LEVEL",
    "BRAIN_LLM_TIMEOUT_SECONDS",
    "BRAIN_ES_URL",
    "BRAIN_ES_USER",
    "BRAIN_ES_PASS",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
)

# Pytest imports `conftest.py` before collecting test modules. Keep unit tests
# independent from local real credentials and `.env` values, including values
# already loaded by pytest plugins before fixtures execute.
for env_key in TEST_LOCAL_ENV_KEYS:
    os.environ.pop(env_key, None)
os.environ["BRAIN_ENV_FILE"] = ""


@pytest.fixture(autouse=True)
def reset_settings_cache(monkeypatch: pytest.MonkeyPatch):
    """Ensure each test sees a fresh settings load.

    Tests that mutate env via monkeypatch can rely on `get_settings()` being
    invalidated between tests.
    """
    for env_key in TEST_LOCAL_ENV_KEYS:
        monkeypatch.delenv(env_key, raising=False)
    monkeypatch.setenv("BRAIN_ENV_FILE", "")
    get_settings.cache_clear()
    get_langfuse_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_langfuse_client.cache_clear()
