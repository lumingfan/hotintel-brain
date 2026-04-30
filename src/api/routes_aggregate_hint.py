"""POST /v1/aggregate-hint — event aggregation hint entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from src.common.config import get_settings
from src.common.models import AggregateHintRequest, AggregateHintResult
from src.llm.client import aggregate_hint
from src.observability.langfuse_client import get_prompt_definition

router = APIRouter()

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "aggregate_hint_v1.md"


def _render_user_prompt(request: AggregateHintRequest) -> str:
    candidate_blocks = []
    for event in request.candidateEvents:
        candidate_blocks.append(
            "\n".join(
                [
                    f"- eventId: {event.eventId}",
                    f"  canonicalTitle: {event.canonicalTitle}",
                    f"  canonicalSummary: {event.canonicalSummary}",
                    f"  sources: {event.sources}",
                ]
            )
        )

    return (
        "New hotspot:\n"
        f"- id: {request.newHotspot.id}\n"
        f"  title: {request.newHotspot.title}\n"
        f"  content: {request.newHotspot.content}\n"
        f"  source: {request.newHotspot.source}\n\n"
        "Candidate events:\n"
        f"{chr(10).join(candidate_blocks)}\n"
    )


async def run_aggregate_hint(request: AggregateHintRequest) -> AggregateHintResult:
    settings = get_settings()
    model_name = request.forceModel or settings.brain_default_model
    prompt = get_prompt_definition("aggregate-hint", _PROMPT_PATH, "aggregate-hint-v1.0")
    output, _, latency_ms, trace_id = await aggregate_hint(
        model_name=model_name,
        system_prompt=prompt.text,
        user_prompt=_render_user_prompt(request),
        prompt_definition=prompt,
    )
    return AggregateHintResult(
        decision=output.decision,
        matchedEventId=output.matchedEventId,
        confidence=output.confidence,
        reasoning=output.reasoning,
        alternativeMatches=output.alternativeMatches,
        model=model_name,
        promptVersion=prompt.version,
        latencyMs=latency_ms,
        traceId=trace_id,
    )


@router.post("/aggregate-hint", response_model=AggregateHintResult)
async def aggregate_hint_route(request: AggregateHintRequest) -> AggregateHintResult:
    return await run_aggregate_hint(request)
