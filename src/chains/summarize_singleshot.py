"""Summarize chain entrypoints."""

from __future__ import annotations

from pathlib import Path

from src.common.config import get_settings
from src.common.models import SummarizeRequest, SummarizeResult
from src.common.prompt_loader import load_markdown_prompt
from src.llm.client import summarize_document
from src.observability.langfuse_client import get_prompt_definition

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "summarize_v1.md"


def _load_summarize_prompt() -> tuple[str, str]:
    return load_markdown_prompt(_PROMPT_PATH, "summarize-v1.0")


def _render_user_prompt(request: SummarizeRequest) -> str:
    hotspot_blocks = []
    for hotspot in request.hotspots:
        hotspot_blocks.append(
            "\n".join(
                [
                    f"  - id: {hotspot.id}",
                    f"    source: {hotspot.source}",
                    f"    publishedAt: {hotspot.publishedAt}",
                    f"    title: {hotspot.title}",
                    f"    content: {hotspot.content}",
                ]
            )
        )
    hotspots_text = "\n".join(hotspot_blocks)

    return (
        f"Topic: {request.topicName}\n"
        f"Style: {request.style.value}\n"
        f"Length hint: {request.lengthHint.value}\n\n"
        "Hot-spots:\n"
        f"{hotspots_text}\n"
    )


async def run_summarize(request: SummarizeRequest) -> SummarizeResult:
    settings = get_settings()
    model_name = request.forceModel or settings.brain_default_model
    prompt = get_prompt_definition("summarize", _PROMPT_PATH, "summarize-v1.0")
    prompt_version, system_prompt = prompt.version, prompt.text
    user_prompt = _render_user_prompt(request)

    output, token_usage, latency_ms, trace_id = await summarize_document(
        model_name=model_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_definition=prompt,
    )

    return SummarizeResult(
        summary=output.summary,
        keyPoints=output.keyPoints,
        model=model_name,
        promptVersion=prompt_version,
        latencyMs=latency_ms,
        tokenUsage=token_usage,
        traceId=trace_id,
    )
