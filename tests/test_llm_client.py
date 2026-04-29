"""Whitelist & reachability tests for the LLM client.

V1 first batch: no real LLM calls. We just enforce ADR 0006 invariants.
"""

from __future__ import annotations

import litellm
import pytest

from src.common.config import get_settings
from src.llm.client import (
    SUPPORTED_MODELS_V1,
    Provider,
    UnsupportedModelError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
    _build_async_instructor_client,
    _provider_completion_kwargs,
    is_model_reachable,
    judge_document,
    resolve_model,
    supported_model_names,
)
from src.observability.langfuse_client import PromptDefinition


def test_v1_whitelist_only_contains_gpt_and_claude() -> None:
    """ADR 0006: no third-party / domestic models in V1."""
    for name, descriptor in SUPPORTED_MODELS_V1.items():
        assert descriptor.provider in (Provider.OPENAI, Provider.ANTHROPIC)
        if descriptor.provider is Provider.OPENAI:
            assert name.startswith("gpt-")
        if descriptor.provider is Provider.ANTHROPIC:
            assert name.startswith("claude-")


def test_v1_default_model_is_gpt_4o_mini() -> None:
    default_models = [
        name for name, d in SUPPORTED_MODELS_V1.items() if "V1-default" in d.is_default_for
    ]
    assert default_models == ["gpt-4o-mini"]


def test_resolve_model_returns_descriptor() -> None:
    descriptor = resolve_model("gpt-4o-mini")
    assert descriptor.provider is Provider.OPENAI


def test_resolve_model_rejects_unknown() -> None:
    with pytest.raises(UnsupportedModelError):
        resolve_model("deepseek-chat")


def test_supported_model_names_sorted() -> None:
    names = supported_model_names()
    assert names == sorted(names)


def test_is_reachable_false_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    assert is_model_reachable("gpt-4o-mini") is False
    assert is_model_reachable("claude-3-5-haiku-latest") is False


def test_is_reachable_true_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    assert is_model_reachable("gpt-4o-mini") is True
    # Anthropic key still missing — should be False.
    assert is_model_reachable("claude-3-5-haiku-latest") is False


def test_is_reachable_false_for_unknown_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    assert is_model_reachable("deepseek-chat") is False


def test_openai_completion_kwargs_include_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:17654")
    get_settings.cache_clear()

    kwargs = _provider_completion_kwargs("gpt-4o-mini")

    assert kwargs["api_key"] == "sk-test"
    assert kwargs["base_url"] == "http://localhost:17654"


def test_anthropic_completion_kwargs_do_not_include_openai_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:17654")
    get_settings.cache_clear()

    kwargs = _provider_completion_kwargs("claude-3-5-haiku-latest")

    assert kwargs["api_key"] == "sk-ant-test"
    assert "base_url" not in kwargs


def test_openai_instructor_client_uses_json_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_from_litellm(completion, mode, **kwargs):
        captured["completion"] = completion
        captured["mode"] = mode
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr("src.llm.client.instructor.from_litellm", fake_from_litellm)

    _build_async_instructor_client("gpt-4o-mini")

    assert captured["mode"].value == "json_mode"


@pytest.mark.asyncio
async def test_judge_document_maps_litellm_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        async def create_with_completion(self, **kwargs):
            raise litellm.Timeout("timeout", "gpt-4o-mini", "openai")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    monkeypatch.setattr("src.llm.client._build_async_instructor_client", lambda model_name: FakeClient())

    with pytest.raises(UpstreamTimeoutError):
        await judge_document(
            model_name="gpt-4o-mini",
            system_prompt="sys",
            user_prompt="user",
            prompt_definition=PromptDefinition(
                name="judge",
                version="judge-v1.0",
                text="prompt",
                source="local",
            ),
        )


@pytest.mark.asyncio
async def test_judge_document_maps_litellm_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        async def create_with_completion(self, **kwargs):
            raise litellm.RateLimitError("rate limited", "openai", "gpt-4o-mini")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    monkeypatch.setattr("src.llm.client._build_async_instructor_client", lambda model_name: FakeClient())

    with pytest.raises(UpstreamRateLimitError):
        await judge_document(
            model_name="gpt-4o-mini",
            system_prompt="sys",
            user_prompt="user",
            prompt_definition=PromptDefinition(
                name="judge",
                version="judge-v1.0",
                text="prompt",
                source="local",
            ),
        )
