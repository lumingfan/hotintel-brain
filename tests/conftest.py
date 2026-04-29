"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from src.common.config import get_settings
from src.observability.langfuse_client import get_langfuse_client


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Ensure each test sees a fresh settings load.

    Tests that mutate env via monkeypatch can rely on `get_settings()` being
    invalidated between tests.
    """
    yield
    get_settings.cache_clear()
    get_langfuse_client.cache_clear()
