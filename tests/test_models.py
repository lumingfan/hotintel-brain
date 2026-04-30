"""Pydantic schema sanity tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.common.config import get_settings
from src.common.models import (
    AggregateHintRequest,
    AggregateHintResult,
    AggregateHintVerdict,
    EmbedRequest,
    EmbedResponse,
    EmbedVector,
    EventSummary,
    ExpandRequest,
    ExpandResult,
    FollowUpHintRequest,
    FollowUpHintResult,
    FollowUpStatus,
    ImportanceLevel,
    JudgeBatchItem,
    JudgeBatchRequest,
    JudgeBatchResult,
    JudgementLayer,
    JudgementOutput,
    JudgementResult,
    RawDocument,
    SummarizeRequest,
    SummaryStyle,
    TokenUsage,
    TopicContext,
    TopicRule,
    TriageHintRequest,
    TriageHintResult,
    TriageStatus,
)


def _sample_judge_output(**overrides: object) -> JudgementOutput:
    payload = dict(
        relevanceScore=85,
        isReal=True,
        isRealConfidence=0.9,
        importance=ImportanceLevel.HIGH,
        summary="测试摘要",
        keywordMentioned=True,
        reasoning="Hits primary keyword in title.",
        expandedKeywords=["A", "B"],
    )
    payload.update(overrides)  # type: ignore[arg-type]
    return JudgementOutput(**payload)


def test_judgement_output_roundtrip() -> None:
    output = _sample_judge_output()
    assert output.importance is ImportanceLevel.HIGH
    assert output.relevanceScore == 85


def test_judgement_output_relevance_bounds() -> None:
    with pytest.raises(ValidationError):
        _sample_judge_output(relevanceScore=120)


def test_judgement_output_summary_length() -> None:
    too_long = "x" * 250
    with pytest.raises(ValidationError):
        _sample_judge_output(summary=too_long)


def test_judgement_result_from_output_marks_not_partial() -> None:
    output = _sample_judge_output()
    result = JudgementResult.from_output(
        rawDocumentId="rd_001",
        layer=JudgementLayer.L1,
        model="gpt-4o-mini",
        promptVersion="judge-v1.0",
        output=output,
        latencyMs=820,
        tokenUsage=TokenUsage(promptTokens=600, completionTokens=180, totalTokens=780),
        traceId="br_test",
    )
    assert result.partial is False
    assert result.errorCode is None
    assert result.relevanceScore == 85
    assert result.summary == "测试摘要"


def test_judgement_result_downgrade() -> None:
    result = JudgementResult.downgrade(
        rawDocumentId="rd_001",
        layer=JudgementLayer.L1,
        model="gpt-4o-mini",
        promptVersion="judge-v1.0",
        errorCode="SCHEMA_INVALID",
        errorMessage="Output failed schema validation",
        rawModelOutput="...",
    )
    assert result.partial is True
    assert result.errorCode == "SCHEMA_INVALID"
    assert result.relevanceScore is None


def test_topic_rule_default_min_relevance() -> None:
    assert TopicRule().minRelevanceScore == 60


def test_topic_context_requires_primary_keyword() -> None:
    with pytest.raises(ValidationError):
        TopicContext(  # type: ignore[call-arg]
            topicId="tp_001",
            topicName="X",
        )


def test_summarize_request_default_style() -> None:
    request = SummarizeRequest(
        topicId="tp_001",
        topicName="AI Coding Models",
        hotspots=[],
    )
    assert request.style is SummaryStyle.EVENT_DETAIL


def test_raw_document_minimal_fields() -> None:
    doc = RawDocument(
        id="rd_001",
        title="t",
        content="c",
        source="hackernews",
    )
    assert doc.publishedAt is None
    assert doc.url is None


def test_settings_expose_l2_model_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_EMBED_MODEL_PATH", "models/bge-m3")
    monkeypatch.setenv("BRAIN_RERANK_MODEL_PATH", "models/bge-reranker-v2-m3")
    monkeypatch.setenv("BRAIN_DEVICE", "mps")
    monkeypatch.setenv("BRAIN_RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    monkeypatch.setenv("BRAIN_ES_INDEX_NAME", "hotspot_search")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.brain_embed_model_path == "models/bge-m3"
    assert settings.brain_rerank_model_path == "models/bge-reranker-v2-m3"
    assert settings.brain_device == "mps"
    assert settings.brain_rabbitmq_url == "amqp://guest:guest@localhost:5672/"
    assert settings.brain_es_index_name == "hotspot_search"


def test_embed_request_accepts_texts_and_topic_hint() -> None:
    request = EmbedRequest(texts=["Claude Code ships"], topicId="tp_001")
    assert request.texts == ["Claude Code ships"]
    assert request.topicId == "tp_001"


def test_embed_response_roundtrip() -> None:
    response = EmbedResponse(
        model="bge-m3",
        dimension=1024,
        items=[
            EmbedVector(
                text="Claude Code ships",
                vector=[0.1, 0.2, 0.3],
            )
        ],
        traceId="tr_embed",
    )
    assert response.dimension == 1024
    assert response.items[0].vector == [0.1, 0.2, 0.3]


def test_judge_batch_request_requires_items() -> None:
    with pytest.raises(ValidationError):
        JudgeBatchRequest(items=[])  # type: ignore[arg-type]


def test_judge_batch_result_counts() -> None:
    item = JudgeBatchItem(
        rawDocument=RawDocument(
            id="rd_001",
            title="Claude Code remote MCP",
            content="Anthropic shipped remote MCP support.",
            source="hackernews",
        ),
        topicContext=TopicContext(
            topicId="tp_001",
            topicName="AI Coding Models",
            primaryKeyword="Claude Code",
        ),
    )
    request = JudgeBatchRequest(items=[item], maxConcurrency=2)
    result = JudgeBatchResult(results=[], totalLatencyMs=12, successCount=1, partialCount=0)
    assert request.maxConcurrency == 2
    assert result.successCount == 1


def test_expand_request_accepts_existing_keywords() -> None:
    request = ExpandRequest(
        topicId="tp_001",
        topicName="AI Coding Models",
        primaryKeyword="Claude Code",
        existingExpandedKeywords=["Anthropic", "MCP"],
        limit=8,
    )
    assert request.limit == 8
    assert request.existingExpandedKeywords == ["Anthropic", "MCP"]


def test_expand_result_carries_prompt_metadata() -> None:
    result = ExpandResult(
        expandedKeywords=["Claude CLI", "Anthropic MCP"],
        model="gpt-4o-mini",
        promptVersion="expand-v1.0",
        latencyMs=55,
        traceId="tr_expand",
    )
    assert result.promptVersion == "expand-v1.0"


def test_aggregate_hint_request_accepts_candidate_events() -> None:
    request = AggregateHintRequest(
        newHotspot=RawDocument(
            id="hs_001",
            title="Claude Code ships remote MCP",
            content="Anthropic announced support.",
            source="weibo",
        ),
        candidateEvents=[
            EventSummary(
                eventId="evt_001",
                canonicalTitle="Claude Code remote MCP support",
                canonicalSummary="Remote MCP support shipped.",
                sources=["hackernews"],
            )
        ],
    )
    assert request.candidateEvents[0].eventId == "evt_001"


def test_aggregate_hint_result_supports_merge_decision() -> None:
    result = AggregateHintResult(
        decision=AggregateHintVerdict.MERGE_INTO_EXISTING,
        matchedEventId="evt_001",
        confidence=0.91,
        reasoning="Same release event.",
        alternativeMatches=[],
        model="gpt-4o-mini",
        promptVersion="aggregate-hint-v1.0",
        latencyMs=66,
    )
    assert result.decision is AggregateHintVerdict.MERGE_INTO_EXISTING


def test_triage_hint_request_accepts_event_summary() -> None:
    request = TriageHintRequest(
        event=EventSummary(
            eventId="evt_001",
            topicId="tp_001",
            topicName="AI Coding Models",
            canonicalTitle="Claude Code remote MCP support",
            canonicalSummary="Anthropic shipped support.",
            topImportanceLevel="high",
            topRelevanceScore=91,
            hotspotCount=3,
            sourceCount=2,
        ),
    )
    assert request.event.topicName == "AI Coding Models"


def test_triage_hint_result_supports_recommendation() -> None:
    result = TriageHintResult(
        recommendedTriageStatus=TriageStatus.CONFIRMED,
        confidence=0.82,
        reasoning="Multiple high-confidence sources.",
        alternativeStatuses=[],
        model="gpt-4o-mini",
        promptVersion="triage-hint-v1.0",
        latencyMs=77,
    )
    assert result.recommendedTriageStatus is TriageStatus.CONFIRMED


def test_follow_up_hint_request_accepts_event_summary() -> None:
    request = FollowUpHintRequest(
        event=EventSummary(
            eventId="evt_001",
            topicId="tp_001",
            topicName="AI Coding Models",
            canonicalTitle="Claude Code remote MCP support",
            canonicalSummary="Anthropic shipped it.",
            sources=["hackernews"],
            triageStatus=TriageStatus.REVIEWING,
            currentFollowUpStatus=FollowUpStatus.NONE,
        )
    )
    assert request.event.currentFollowUpStatus is FollowUpStatus.NONE


def test_follow_up_hint_result_caps_actions() -> None:
    with pytest.raises(ValidationError):
        FollowUpHintResult(
            recommendedFollowUpStatus=FollowUpStatus.NEEDS_FOLLOW_UP,
            suggestedActions=["one", "two", "three", "four"],
            confidence=0.8,
            reasoning="Need more evidence before acting.",
            model="gpt-4o-mini",
            promptVersion="follow-up-hint-v1.0",
            fallbackUsed=False,
        )
