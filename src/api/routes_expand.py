"""POST /v1/expand — keyword expansion entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from src.common.config import get_settings
from src.common.models import ExpandRequest, ExpandResult
from src.llm.client import expand_keywords
from src.observability.langfuse_client import get_prompt_definition

router = APIRouter()

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "expand_v1.md"


def _render_user_prompt(request: ExpandRequest) -> str:
    return (
        f"Topic: {request.topicName}\n"
        f"Primary keyword: {request.primaryKeyword}\n"
        f"Existing expanded keywords: {request.existingExpandedKeywords}\n"
        f"Limit: {request.limit}\n"
    )


async def run_expand(request: ExpandRequest) -> ExpandResult:
    settings = get_settings()
    model_name = request.forceModel or settings.brain_default_model
    prompt = get_prompt_definition("expand", _PROMPT_PATH, "expand-v1.0")
    output, _, latency_ms, trace_id = await expand_keywords(
        model_name=model_name,
        system_prompt=prompt.text,
        user_prompt=_render_user_prompt(request),
        prompt_definition=prompt,
    )
    return ExpandResult(
        expandedKeywords=output.expandedKeywords[: request.limit],
        model=model_name,
        promptVersion=prompt.version,
        latencyMs=latency_ms,
        traceId=trace_id,
    )


@router.post("/expand", response_model=ExpandResult)
async def expand(request: ExpandRequest) -> ExpandResult:
    return await run_expand(request)
