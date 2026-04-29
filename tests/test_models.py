"""Pydantic schema sanity tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.common.models import (
    ImportanceLevel,
    JudgementLayer,
    JudgementOutput,
    JudgementResult,
    RawDocument,
    SummarizeRequest,
    SummaryStyle,
    TokenUsage,
    TopicContext,
    TopicRule,
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
