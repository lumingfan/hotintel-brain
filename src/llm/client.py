"""LLM client abstraction for V1.

This module keeps the provider whitelist, cheap reachability checks, and the
first structured-output entrypoint for `POST /v1/judge`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter
from typing import Any

import instructor
import litellm
from instructor.core import InstructorRetryException, ValidationError
from litellm import acompletion

from src.common.config import get_settings
from src.common.models import JudgementOutput, SummarizeOutput, TokenUsage
from src.observability.langfuse_client import (
    PromptDefinition,
    generation_trace,
    update_generation_error,
    update_generation_success,
)


class Provider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass(frozen=True)
class ModelDescriptor:
    name: str
    provider: Provider
    is_default_for: tuple[str, ...] = ()  # e.g. ("V1-default",)


# ADR 0006: V1 only ships these. Adding a model means writing an ADR.
SUPPORTED_MODELS_V1: dict[str, ModelDescriptor] = {
    "gpt-4o-mini": ModelDescriptor(
        name="gpt-4o-mini",
        provider=Provider.OPENAI,
        is_default_for=("V1-default",),
    ),
    "gpt-4o": ModelDescriptor(name="gpt-4o", provider=Provider.OPENAI),
    "claude-3-5-haiku-latest": ModelDescriptor(
        name="claude-3-5-haiku-latest",
        provider=Provider.ANTHROPIC,
    ),
    "claude-3-5-sonnet-latest": ModelDescriptor(
        name="claude-3-5-sonnet-latest",
        provider=Provider.ANTHROPIC,
    ),
}


class UnsupportedModelError(ValueError):
    """Requested model is not in the V1 whitelist (see ADR 0006)."""


class ModelUnavailableError(RuntimeError):
    """Requested model cannot be called in the current environment."""

    def __init__(self, model_name: str):
        super().__init__(
            f"Model {model_name!r} is not reachable in the current environment. "
            "Check the provider API key configuration."
        )
        self.model_name = model_name


class StructuredOutputError(RuntimeError):
    """Structured output could not be validated after instructor retry."""

    def __init__(self, message: str, *, raw_model_output: str | None = None):
        super().__init__(message)
        self.raw_model_output = raw_model_output


class UpstreamTimeoutError(RuntimeError):
    """LLM provider timed out before returning a response."""


class UpstreamRateLimitError(RuntimeError):
    """LLM provider rejected the request due to rate limiting."""


def supported_model_names() -> list[str]:
    return sorted(SUPPORTED_MODELS_V1.keys())


def resolve_model(name: str) -> ModelDescriptor:
    """Validate the model name and return its descriptor."""
    descriptor = SUPPORTED_MODELS_V1.get(name)
    if descriptor is None:
        raise UnsupportedModelError(
            f"Model {name!r} is not in V1 whitelist. "
            f"Supported: {', '.join(supported_model_names())}. "
            f"See ADR 0006."
        )
    return descriptor


def is_model_reachable(name: str | None = None) -> bool:
    """Cheap pre-flight check.

    V1 first batch: only checks that the relevant API key env var is set.
    Real connectivity ping (a single dummy completion) lands in batch 2.
    """
    settings = get_settings()
    target = name or settings.brain_default_model
    try:
        descriptor = resolve_model(target)
    except UnsupportedModelError:
        return False
    if descriptor.provider is Provider.OPENAI:
        return settings.openai_enabled
    if descriptor.provider is Provider.ANTHROPIC:
        return settings.anthropic_enabled
    return False


def _provider_completion_kwargs(model_name: str) -> dict[str, object]:
    settings = get_settings()
    descriptor = resolve_model(model_name)
    if descriptor.provider is Provider.OPENAI:
        kwargs = {
            "api_key": settings.openai_api_key,
            "timeout": settings.brain_llm_timeout_seconds,
        }
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        return kwargs
    if descriptor.provider is Provider.ANTHROPIC:
        return {
            "api_key": settings.anthropic_api_key,
            "timeout": settings.brain_llm_timeout_seconds,
        }
    return {"api_key": "", "timeout": settings.brain_llm_timeout_seconds}


def _build_async_instructor_client(model_name: str) -> instructor.AsyncInstructor:
    descriptor = resolve_model(model_name)
    mode = instructor.Mode.JSON
    if descriptor.provider is Provider.ANTHROPIC:
        mode = instructor.Mode.ANTHROPIC_JSON
    return instructor.from_litellm(acompletion, mode=mode)


def _stringify_raw_completion(raw_completion: Any) -> str | None:
    if raw_completion is None:
        return None
    message = getattr(raw_completion, "choices", None)
    if message is not None:
        return str(raw_completion)
    return str(raw_completion)


def _extract_token_usage(raw_completion: Any) -> TokenUsage:
    usage = getattr(raw_completion, "usage", None)
    if usage is None:
        return TokenUsage()

    def _read(name: str) -> int:
        if isinstance(usage, dict):
            value = usage.get(name, 0)
        else:
            value = getattr(usage, name, 0)
        return int(value or 0)

    prompt_tokens = _read("prompt_tokens")
    completion_tokens = _read("completion_tokens")
    total_tokens = _read("total_tokens")
    return TokenUsage(
        promptTokens=prompt_tokens,
        completionTokens=completion_tokens,
        totalTokens=total_tokens,
    )


async def judge_document(
    *,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    prompt_definition: PromptDefinition,
) -> tuple[JudgementOutput, TokenUsage, int, str | None]:
    """Run the V1 judge prompt through instructor + LiteLLM."""

    completion_kwargs = _provider_completion_kwargs(model_name)
    api_key = completion_kwargs["api_key"]
    if not api_key:
        raise ModelUnavailableError(model_name)

    client = _build_async_instructor_client(model_name)
    started_at = perf_counter()
    with generation_trace(
        name="judge",
        model=model_name,
        prompt_definition=prompt_definition,
        input_payload={"system": system_prompt, "user": user_prompt},
    ) as trace_id:
        try:
            output, raw_completion = await client.create_with_completion(
                response_model=JudgementOutput,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model_name,
                max_retries=1,
                **completion_kwargs,
            )
        except litellm.Timeout as exc:
            update_generation_error(error_message=str(exc))
            raise UpstreamTimeoutError(str(exc)) from exc
        except litellm.RateLimitError as exc:
            update_generation_error(error_message=str(exc))
            raise UpstreamRateLimitError(str(exc)) from exc
        except (InstructorRetryException, ValidationError) as exc:
            raw_output = _stringify_raw_completion(getattr(exc, "last_completion", None))
            update_generation_error(error_message=str(exc), raw_output=raw_output)
            raise StructuredOutputError(str(exc), raw_model_output=raw_output) from exc

        latency_ms = int((perf_counter() - started_at) * 1000)
        token_usage = _extract_token_usage(raw_completion)
        update_generation_success(output=output.model_dump(), token_usage=token_usage)
        return output, token_usage, latency_ms, trace_id


async def summarize_document(
    *,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    prompt_definition: PromptDefinition,
) -> tuple[SummarizeOutput, TokenUsage, int, str | None]:
    """Run the V1 summarize prompt through instructor + LiteLLM."""

    completion_kwargs = _provider_completion_kwargs(model_name)
    api_key = completion_kwargs["api_key"]
    if not api_key:
        raise ModelUnavailableError(model_name)

    client = _build_async_instructor_client(model_name)
    started_at = perf_counter()
    with generation_trace(
        name="summarize",
        model=model_name,
        prompt_definition=prompt_definition,
        input_payload={"system": system_prompt, "user": user_prompt},
    ) as trace_id:
        try:
            output, raw_completion = await client.create_with_completion(
                response_model=SummarizeOutput,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=model_name,
                max_retries=1,
                **completion_kwargs,
            )
        except litellm.Timeout as exc:
            update_generation_error(error_message=str(exc))
            raise UpstreamTimeoutError(str(exc)) from exc
        except litellm.RateLimitError as exc:
            update_generation_error(error_message=str(exc))
            raise UpstreamRateLimitError(str(exc)) from exc
        except (InstructorRetryException, ValidationError) as exc:
            raw_output = _stringify_raw_completion(getattr(exc, "last_completion", None))
            update_generation_error(error_message=str(exc), raw_output=raw_output)
            raise StructuredOutputError(str(exc), raw_model_output=raw_output) from exc

        latency_ms = int((perf_counter() - started_at) * 1000)
        token_usage = _extract_token_usage(raw_completion)
        update_generation_success(output=output.model_dump(), token_usage=token_usage)
        return output, token_usage, latency_ms, trace_id
