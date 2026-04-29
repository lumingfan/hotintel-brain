"""L1 single-shot chain entrypoints."""

from __future__ import annotations

from pathlib import Path

from src.common.config import get_settings
from src.common.models import JudgementLayer, JudgementResult, JudgeRequest
from src.common.prompt_loader import load_markdown_prompt
from src.llm.client import StructuredOutputError, judge_document
from src.observability.langfuse_client import get_prompt_definition

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "judge_v1.md"


def _load_judge_prompt() -> tuple[str, str]:
    return load_markdown_prompt(_PROMPT_PATH, "judge-v1.0")


def _render_user_prompt(request: JudgeRequest) -> str:
    doc = request.rawDocument
    topic = request.topicContext
    return (
        f"Topic: {topic.topicName}\n"
        f"Primary keyword: {topic.primaryKeyword}\n"
        f"Expanded keywords: {topic.expandedKeywords}\n"
        "Topic rule:\n"
        f"  - minimum relevance score: {topic.rule.minRelevanceScore}\n"
        f"  - require direct keyword mention: {topic.rule.requireDirectKeywordMention}\n\n"
        "Document:\n"
        f"  - id: {doc.id}\n"
        f"  - source: {doc.source}\n"
        f"  - publishedAt: {doc.publishedAt}\n"
        f"  - title: {doc.title}\n"
        f"  - content: {doc.content}\n"
    )


async def run_judge(request: JudgeRequest) -> JudgementResult:
    """Run the V1 judge chain and downgrade schema failures."""

    settings = get_settings()
    model_name = request.forceModel or settings.brain_default_model
    prompt = get_prompt_definition("judge", _PROMPT_PATH, "judge-v1.0")
    prompt_version, system_prompt = prompt.version, prompt.text
    user_prompt = _render_user_prompt(request)

    try:
        output, token_usage, latency_ms, trace_id = await judge_document(
            model_name=model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_definition=prompt,
        )
    except StructuredOutputError as exc:
        return JudgementResult.downgrade(
            rawDocumentId=request.rawDocument.id,
            layer=JudgementLayer.L1,
            model=model_name,
            promptVersion=prompt_version,
            errorCode="SCHEMA_INVALID",
            errorMessage=str(exc),
            rawModelOutput=exc.raw_model_output,
            traceId=None,
        )

    return JudgementResult.from_output(
        rawDocumentId=request.rawDocument.id,
        layer=JudgementLayer.L1,
        model=model_name,
        promptVersion=prompt_version,
        output=output,
        latencyMs=latency_ms,
        tokenUsage=token_usage,
        traceId=trace_id,
    )
