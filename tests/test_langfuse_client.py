"""Langfuse client tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import respx
from httpx import Response

from src.common.config import get_settings
from src.observability.langfuse_client import get_prompt_definition, is_reachable


@respx.mock
def test_langfuse_is_reachable_pings_public_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    get_settings.cache_clear()

    route = respx.get("http://localhost:3000/api/public/health").mock(
        return_value=Response(200, json={"status": "ok"})
    )

    assert is_reachable() is True
    assert route.called


def test_get_prompt_definition_falls_back_to_local_file_when_unconfigured() -> None:
    prompt = get_prompt_definition(
        "judge",
        Path("prompts/judge_v1.md"),
        "judge-v1.0",
    )

    assert prompt.source == "local"
    assert prompt.version == "judge-v1.0"
    assert "HotIntel Brain" in prompt.text


def test_get_prompt_definition_uses_langfuse_prompt_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePrompt:
        version = 12

        def compile(self) -> str:
            return "remote prompt body"

    class FakeClient:
        def get_prompt(self, name: str, **kwargs):
            assert name == "judge"
            assert kwargs["type"] == "text"
            return FakePrompt()

    monkeypatch.setattr(
        "src.observability.langfuse_client.get_langfuse_client",
        lambda: FakeClient(),
    )

    prompt = get_prompt_definition(
        "judge",
        Path("prompts/judge_v1.md"),
        "judge-v1.0",
    )

    assert prompt.source == "langfuse"
    assert prompt.version == "12"
    assert prompt.text == "remote prompt body"
    assert prompt.prompt_client is not None
