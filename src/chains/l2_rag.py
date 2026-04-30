"""L2 RAG-augmented judge chain."""

from __future__ import annotations

from pathlib import Path

from src.chains.l1_singleshot import run_judge
from src.common.config import get_settings
from src.common.models import JudgementLayer, JudgementResult, JudgeRequest
from src.llm.client import StructuredOutputError, judge_document
from src.observability.langfuse_client import get_prompt_definition
from src.retrieval.retriever import get_retriever

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "judge_v1.md"


def _render_user_prompt(request: JudgeRequest, context: str) -> str:
    doc = request.rawDocument
    topic = request.topicContext
    return (
        f"Topic: {topic.topicName}\n"
        f"Primary keyword: {topic.primaryKeyword}\n"
        f"Expanded keywords: {topic.expandedKeywords}\n"
        "Topic rule:\n"
        f"  - minimum relevance score: {topic.rule.minRelevanceScore}\n"
        f"  - require direct keyword mention: {topic.rule.requireDirectKeywordMention}\n\n"
        "Retrieved context:\n"
        f"{context or '[empty]'}\n\n"
        "Document:\n"
        f"  - id: {doc.id}\n"
        f"  - source: {doc.source}\n"
        f"  - publishedAt: {doc.publishedAt}\n"
        f"  - title: {doc.title}\n"
        f"  - content: {doc.content}\n"
    )


async def run_judge_l2(request: JudgeRequest) -> JudgementResult:
    settings = get_settings()
    model_name = request.forceModel or settings.brain_default_model
    prompt = get_prompt_definition("judge", _PROMPT_PATH, "judge-v1.0")
    prompt_version, system_prompt = prompt.version, prompt.text

    try:
        retrieval = await get_retriever().retrieve(
            topic_id=request.topicContext.topicId,
            query_text=f"{request.rawDocument.title}\n{request.rawDocument.content}",
            top_k=5,
        )
    except Exception:
        return await run_judge(request)

    if not retrieval.items:
        return await run_judge(request)

    user_prompt = _render_user_prompt(request, retrieval.context)
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
            layer=JudgementLayer.L2,
            model=model_name,
            promptVersion=prompt_version,
            errorCode="SCHEMA_INVALID",
            errorMessage=str(exc),
            rawModelOutput=exc.raw_model_output,
            traceId=None,
        )

    return JudgementResult.from_output(
        rawDocumentId=request.rawDocument.id,
        layer=JudgementLayer.L2,
        model=model_name,
        promptVersion=prompt_version,
        output=output,
        latencyMs=latency_ms,
        tokenUsage=token_usage,
        traceId=trace_id,
    )
