"""POST /v1/triage-hint — triage recommendation entrypoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from src.common.config import get_settings
from src.common.models import TriageHintRequest, TriageHintResult
from src.llm.client import triage_hint
from src.observability.langfuse_client import get_prompt_definition

router = APIRouter()

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "triage_hint_v1.md"


def _render_user_prompt(request: TriageHintRequest) -> str:
    event = request.event
    return (
        f"Topic: {event.topicName}\n"
        f"Event title: {event.canonicalTitle}\n"
        f"Event summary: {event.canonicalSummary}\n"
        f"Importance: {event.topImportanceLevel}\n"
        f"Relevance score: {event.topRelevanceScore}\n"
        f"Hotspot count: {event.hotspotCount}\n"
        f"Source count: {event.sourceCount}\n"
        f"Sources: {event.sources}\n"
    )


async def run_triage_hint(request: TriageHintRequest) -> TriageHintResult:
    settings = get_settings()
    model_name = request.forceModel or settings.brain_default_model
    prompt = get_prompt_definition("triage-hint", _PROMPT_PATH, "triage-hint-v1.0")
    output, _, latency_ms, trace_id = await triage_hint(
        model_name=model_name,
        system_prompt=prompt.text,
        user_prompt=_render_user_prompt(request),
        prompt_definition=prompt,
    )
    return TriageHintResult(
        recommendedTriageStatus=output.recommendedTriageStatus,
        confidence=output.confidence,
        reasoning=output.reasoning,
        alternativeStatuses=output.alternativeStatuses,
        model=model_name,
        promptVersion=prompt.version,
        latencyMs=latency_ms,
        traceId=trace_id,
    )


@router.post("/triage-hint", response_model=TriageHintResult)
async def triage_hint_route(request: TriageHintRequest) -> TriageHintResult:
    return await run_triage_hint(request)
