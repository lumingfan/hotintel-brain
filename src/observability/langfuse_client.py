"""Langfuse client wiring and thin project-level wrappers."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from langfuse import Langfuse

from src.common.config import get_settings
from src.common.models import TokenUsage
from src.common.prompt_loader import load_markdown_prompt

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptDefinition:
    name: str
    version: str
    text: str
    source: str
    prompt_client: Any | None = None


@lru_cache(maxsize=1)
def get_langfuse_client() -> Langfuse | None:
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def is_reachable() -> bool:
    """Ping the public Langfuse health endpoint when keys are configured."""

    settings = get_settings()
    if not settings.langfuse_enabled:
        return False

    health_url = f"{settings.langfuse_host.rstrip('/')}/api/public/health"
    try:
        response = httpx.get(health_url, timeout=3.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return False

    try:
        body = response.json()
    except ValueError:
        return False
    return body.get("status") == "ok"


def get_prompt_definition(
    prompt_name: str,
    fallback_path: Path,
    default_version: str,
) -> PromptDefinition:
    """Prefer Langfuse prompt management, with local markdown fallback."""

    fallback_version, fallback_text = load_markdown_prompt(fallback_path, default_version)
    client = get_langfuse_client()
    if client is None:
        return PromptDefinition(
            name=prompt_name,
            version=fallback_version,
            text=fallback_text,
            source="local",
        )

    try:
        prompt_client = client.get_prompt(
            prompt_name,
            type="text",
            fallback=fallback_text,
        )
        prompt_text = prompt_client.compile()
        prompt_version = str(getattr(prompt_client, "version", fallback_version))
        return PromptDefinition(
            name=prompt_name,
            version=prompt_version,
            text=prompt_text,
            source="langfuse",
            prompt_client=prompt_client,
        )
    except Exception:  # pragma: no cover - defensive fallback
        _log.warning(
            "Falling back to local prompt file for %s because Langfuse prompt fetch failed.",
            prompt_name,
            exc_info=True,
        )
        return PromptDefinition(
            name=prompt_name,
            version=fallback_version,
            text=fallback_text,
            source="local",
        )


@contextmanager
def generation_trace(
    *,
    name: str,
    model: str,
    prompt_definition: PromptDefinition,
    input_payload: dict[str, Any],
) -> Iterator[str | None]:
    """Create a Langfuse generation observation when available."""

    client = get_langfuse_client()
    if client is None:
        yield None
        return

    try:
        observation = client.start_as_current_observation(
            name=name,
            as_type="generation",
            input=input_payload,
            model=model,
            version=prompt_definition.version,
            prompt=prompt_definition.prompt_client,
            end_on_exit=True,
        )
    except Exception:  # pragma: no cover - defensive fallback
        _log.warning("Failed to start Langfuse observation for %s.", name, exc_info=True)
        yield None
        return

    with observation:
        yield client.get_current_trace_id()


def update_generation_success(
    *,
    output: Any,
    token_usage: TokenUsage,
) -> None:
    client = get_langfuse_client()
    if client is None:
        return

    try:
        client.update_current_generation(
            output=output,
            usage_details={
                "input": token_usage.promptTokens,
                "output": token_usage.completionTokens,
                "total": token_usage.totalTokens,
            },
        )
    except Exception:  # pragma: no cover - defensive fallback
        _log.warning("Failed to update Langfuse generation success payload.", exc_info=True)


def update_generation_error(*, error_message: str, raw_output: str | None = None) -> None:
    client = get_langfuse_client()
    if client is None:
        return

    try:
        client.update_current_generation(
            output=raw_output or error_message,
            level="ERROR",
            status_message=error_message,
        )
    except Exception:  # pragma: no cover - defensive fallback
        _log.warning("Failed to update Langfuse generation error payload.", exc_info=True)


def trace_disabled_warning() -> None:
    """Log once if traces are configured to be disabled (key not set)."""

    settings = get_settings()
    if not settings.langfuse_enabled:
        _log.info(
            "Langfuse keys are not configured; LLM calls will not be traced. "
            "See infra/langfuse/README.md for setup."
        )
