"""L3 single-agent follow-up intelligence chain."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from src.common.config import get_settings
from src.common.models import (
    EventSummary,
    FollowUpHintOutput,
    FollowUpHintRequest,
    FollowUpHintResult,
    FollowUpStatus,
    TokenUsage,
    TriageStatus,
)
from src.llm.client import ModelUnavailableError, Provider, resolve_model
from src.observability.langfuse_client import (
    generation_trace,
    get_prompt_definition,
    update_generation_error,
    update_generation_success,
)
from src.retrieval.retriever import HybridRetriever, get_retriever
from src.tools.expand_keyword import expand_keyword_candidates
from src.tools.fetch_doc import FetchedDocument, fetch_document_by_id
from src.tools.score_one import FollowUpSubScore, score_document_for_follow_up
from src.tools.search_history import HistoryDoc, search_history_for_topic

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "follow_up_hint_v1.md"

L3_AGENT_USAGE_LIMITS = UsageLimits(
    request_limit=6,
    tool_calls_limit=6,
    total_tokens_limit=2000,
)

_TOOL_LIMITS = {
    "expand_keyword": 1,
    "search_history": 2,
    "fetch_doc": 2,
    "score_one": 2,
}


class ToolLimitExceededError(RuntimeError):
    def __init__(self, tool_name: str):
        super().__init__(f"{tool_name} exceeded its local call cap")
        self.tool_name = tool_name


class ToolExecutionError(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


@dataclass
class ToolCallBudget:
    counts: dict[str, int] = field(default_factory=lambda: {name: 0 for name in _TOOL_LIMITS})

    def consume(self, tool_name: str) -> None:
        limit = _TOOL_LIMITS[tool_name]
        current = self.counts.get(tool_name, 0) + 1
        if current > limit:
            raise ToolLimitExceededError(tool_name)
        self.counts[tool_name] = current


@dataclass
class FollowUpAgentDeps:
    request: FollowUpHintRequest
    tool_budget: ToolCallBudget = field(default_factory=ToolCallBudget)
    retriever: HybridRetriever | None = None
    doc_cache: dict[str, FetchedDocument] = field(default_factory=dict)


def _render_user_prompt(request: FollowUpHintRequest) -> str:
    event = request.event
    return (
        f"Topic: {event.topicName}\n"
        f"Primary keyword: {event.primaryKeyword}\n"
        f"Expanded keywords: {event.expandedKeywords}\n"
        f"Event title: {event.canonicalTitle}\n"
        f"Event summary: {event.canonicalSummary}\n"
        f"Triage status: {event.triageStatus}\n"
        f"Current follow-up status: {event.currentFollowUpStatus}\n"
        f"Current follow-up note: {event.currentFollowUpNote}\n"
        f"Top relevance score: {event.topRelevanceScore}\n"
        f"Hotspot count: {event.hotspotCount}\n"
        f"Source count: {event.sourceCount}\n"
        f"Sources: {event.sources}\n"
    )


def _resolve_agent_model(model_name: str) -> OpenAIModel:
    settings = get_settings()
    descriptor = resolve_model(model_name)
    if descriptor.provider is not Provider.OPENAI:
        raise ModelUnavailableError(model_name)
    if not settings.openai_api_key:
        raise ModelUnavailableError(model_name)
    provider = OpenAIProvider(
        base_url=settings.openai_base_url or None,
        api_key=settings.openai_api_key,
    )
    return OpenAIModel(model_name, provider=provider)


def _build_follow_up_agent(*, model_name: str, prompt_text: str) -> Agent[FollowUpAgentDeps, FollowUpHintOutput]:
    agent = Agent(
        model=_resolve_agent_model(model_name),
        output_type=FollowUpHintOutput,
        deps_type=FollowUpAgentDeps,
        instructions=prompt_text,
        retries=1,
        output_retries=1,
        defer_model_check=True,
    )

    @agent.tool(name="expand_keyword")
    async def expand_keyword(
        ctx: RunContext[FollowUpAgentDeps],
        topic_name: str,
        primary_keyword: str | None = None,
    ) -> list[str]:
        ctx.deps.tool_budget.consume("expand_keyword")
        event = ctx.deps.request.event
        expanded = expand_keyword_candidates(
            topic_name=topic_name,
            primary_keyword=primary_keyword or event.primaryKeyword,
            canonical_title=event.canonicalTitle,
            existing_keywords=event.expandedKeywords,
        )
        if not expanded:
            raise ToolExecutionError("retrieval_empty", "No keyword variants available.")
        return expanded

    @agent.tool(name="search_history")
    async def search_history(
        ctx: RunContext[FollowUpAgentDeps],
        topic_id: str,
        query: str,
        top_k: int = 3,
    ) -> list[HistoryDoc]:
        ctx.deps.tool_budget.consume("search_history")
        hits = await search_history_for_topic(
            topic_id=topic_id,
            query=query,
            top_k=top_k,
            retriever=ctx.deps.retriever or get_retriever(),
            doc_cache=ctx.deps.doc_cache,
        )
        if not hits:
            raise ToolExecutionError("retrieval_empty", "History search returned no supporting documents.")
        return hits

    @agent.tool(name="fetch_doc")
    async def fetch_doc(ctx: RunContext[FollowUpAgentDeps], doc_id: str) -> FetchedDocument:
        ctx.deps.tool_budget.consume("fetch_doc")
        doc = await fetch_document_by_id(doc_id, cache=ctx.deps.doc_cache)
        if doc is None:
            raise ToolExecutionError("fetch_empty", f"Document {doc_id} is not available in the current evidence cache.")
        return doc

    @agent.tool(name="score_one")
    async def score_one(
        ctx: RunContext[FollowUpAgentDeps],
        doc_id: str,
        context: str,
    ) -> FollowUpSubScore:
        ctx.deps.tool_budget.consume("score_one")
        doc = await fetch_document_by_id(doc_id, cache=ctx.deps.doc_cache)
        if doc is None:
            raise ToolExecutionError("fetch_empty", f"Document {doc_id} is not available in the current evidence cache.")
        return score_document_for_follow_up(
            doc=doc,
            context=context,
            event_title=ctx.deps.request.event.canonicalTitle,
            existing_sources=ctx.deps.request.event.sources,
        )

    return agent


async def _execute_agent(
    *,
    agent: Agent[FollowUpAgentDeps, FollowUpHintOutput],
    user_prompt: str,
    deps: FollowUpAgentDeps,
):
    return await agent.run(
        user_prompt,
        deps=deps,
        usage_limits=L3_AGENT_USAGE_LIMITS,
    )


def _usage_to_token_usage(usage: RunUsage) -> TokenUsage:
    return TokenUsage(
        promptTokens=usage.input_tokens,
        completionTokens=usage.output_tokens,
        totalTokens=usage.total_tokens,
    )


def _fallback_status(event: EventSummary) -> FollowUpStatus:
    if event.triageStatus is None:
        return FollowUpStatus.LATER
    if event.triageStatus in {TriageStatus.REVIEWING, TriageStatus.CONFIRMED}:
        return FollowUpStatus.WATCHING
    return FollowUpStatus.LATER


def _fallback_action(status: FollowUpStatus) -> str:
    if status is FollowUpStatus.WATCHING:
        return "Keep the event on watch and wait for another strong source before escalating manual follow-up."
    return "Park the event for later review until more evidence accumulates."


def _classify_error(exception: Exception) -> str:
    if isinstance(exception, UsageLimitExceeded):
        return "usage_limit"
    if isinstance(exception, ToolLimitExceededError):
        return "tool_limit"
    if isinstance(exception, ToolExecutionError):
        return exception.reason
    if isinstance(exception, ModelUnavailableError):
        return "model_unavailable"
    if isinstance(exception, ModelHTTPError):
        message = str(exception).lower()
        if "429" in message or "rate" in message:
            return "rate_limit"
        if "408" in message or "timeout" in message:
            return "timeout"
        return "provider_error"
    if isinstance(exception, UnexpectedModelBehavior):
        return "reasoning_error"
    return "tool_error"


def _fallback_result(
    *,
    request: FollowUpHintRequest,
    model_name: str,
    prompt_version: str,
    latency_ms: int,
    trace_id: str | None,
    fallback_reason: str,
) -> FollowUpHintResult:
    status = _fallback_status(request.event)
    return FollowUpHintResult(
        recommendedFollowUpStatus=status,
        suggestedActions=[_fallback_action(status)],
        confidence=0.35,
        reasoning="The agent fell back to the conservative path because the L3 reasoning loop could not complete safely.",
        model=model_name,
        promptVersion=prompt_version,
        latencyMs=latency_ms,
        traceId=trace_id,
        fallbackUsed=True,
        fallbackReason=fallback_reason,
    )


async def run_follow_up_hint(request: FollowUpHintRequest) -> FollowUpHintResult:
    settings = get_settings()
    model_name = request.forceModel or settings.brain_default_model
    prompt = get_prompt_definition("follow-up-hint", _PROMPT_PATH, "follow-up-hint-v1.0")
    user_prompt = _render_user_prompt(request)
    deps = FollowUpAgentDeps(request=request)
    started_at = perf_counter()

    try:
        agent = _build_follow_up_agent(model_name=model_name, prompt_text=prompt.text)
    except Exception as exc:
        return _fallback_result(
            request=request,
            model_name=model_name,
            prompt_version=prompt.version,
            latency_ms=int((perf_counter() - started_at) * 1000),
            trace_id=None,
            fallback_reason=_classify_error(exc),
        )

    with generation_trace(
        name="follow-up-hint",
        model=model_name,
        prompt_definition=prompt,
        input_payload={"user": user_prompt},
    ) as trace_id:
        try:
            result = await _execute_agent(agent=agent, user_prompt=user_prompt, deps=deps)
        except Exception as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            update_generation_error(error_message=str(exc))
            return _fallback_result(
                request=request,
                model_name=model_name,
                prompt_version=prompt.version,
                latency_ms=latency_ms,
                trace_id=trace_id,
                fallback_reason=_classify_error(exc),
            )

        latency_ms = int((perf_counter() - started_at) * 1000)
        token_usage = _usage_to_token_usage(result.usage())
        update_generation_success(output=result.output.model_dump(), token_usage=token_usage)
        return FollowUpHintResult(
            recommendedFollowUpStatus=result.output.recommendedFollowUpStatus,
            suggestedActions=result.output.suggestedActions,
            confidence=result.output.confidence,
            reasoning=result.output.reasoning,
            model=model_name,
            promptVersion=prompt.version,
            latencyMs=latency_ms,
            traceId=trace_id,
            fallbackUsed=False,
            fallbackReason=None,
        )
