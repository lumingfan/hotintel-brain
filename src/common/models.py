"""Shared Pydantic models for HotIntel Brain.

These mirror the contract documented in `docs/api/contract.md`. Keep this
module the single source of truth for V1 schemas; chains / retrieval / agent
modules import from here.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------
# Enumerations
# ----------------------------------------------------------------------


class ImportanceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class JudgementLayer(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class SummaryStyle(StrEnum):
    DIGEST = "digest"
    REPORT = "report"
    EVENT_DETAIL = "event_detail"


class SummaryLengthHint(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class AggregateHintVerdict(StrEnum):
    MERGE_INTO_EXISTING = "MERGE_INTO_EXISTING"
    CREATE_NEW = "CREATE_NEW"
    UNCERTAIN = "UNCERTAIN"


class TriageStatus(StrEnum):
    NEW = "NEW"
    REVIEWING = "REVIEWING"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"
    ARCHIVED = "ARCHIVED"


# ----------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------


class RawDocument(BaseModel):
    id: str
    title: str
    content: str
    source: str
    publishedAt: datetime | None = None
    author: str | None = None
    url: str | None = None


class TopicRule(BaseModel):
    minRelevanceScore: int = Field(ge=0, le=100, default=60)
    requireDirectKeywordMention: bool = False


class TopicContext(BaseModel):
    topicId: str
    topicName: str
    primaryKeyword: str
    expandedKeywords: list[str] = Field(default_factory=list)
    rule: TopicRule = Field(default_factory=TopicRule)


class JudgeRequest(BaseModel):
    rawDocument: RawDocument
    topicContext: TopicContext
    forceLayer: JudgementLayer | None = None
    forceModel: str | None = None


class JudgeBatchItem(BaseModel):
    rawDocument: RawDocument
    topicContext: TopicContext


class JudgeBatchRequest(BaseModel):
    items: list[JudgeBatchItem] = Field(min_length=1)
    forceLayer: JudgementLayer | None = None
    forceModel: str | None = None
    maxConcurrency: int = Field(default=4, ge=1, le=16)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    topicId: str | None = None


class ExpandRequest(BaseModel):
    topicId: str
    topicName: str
    primaryKeyword: str
    existingExpandedKeywords: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=20)
    forceModel: str | None = None


class EventSummary(BaseModel):
    eventId: str
    canonicalTitle: str
    canonicalSummary: str | None = None
    sources: list[str] = Field(default_factory=list)
    firstSeenAt: datetime | None = None
    lastSeenAt: datetime | None = None
    topicId: str | None = None
    topicName: str | None = None
    topImportanceLevel: str | None = None
    topRelevanceScore: int | None = None
    hotspotCount: int | None = None
    sourceCount: int | None = None
    triageStatus: TriageStatus | None = None
    currentFollowUpStatus: str | None = None
    currentFollowUpNote: str | None = None


class AggregateHintRequest(BaseModel):
    newHotspot: RawDocument
    candidateEvents: list[EventSummary] = Field(min_length=1)
    forceModel: str | None = None


class TriageHintRequest(BaseModel):
    event: EventSummary
    forceModel: str | None = None


# ----------------------------------------------------------------------
# Token / trace metadata
# ----------------------------------------------------------------------


class TokenUsage(BaseModel):
    promptTokens: int = 0
    completionTokens: int = 0
    totalTokens: int = 0


class EmbedVector(BaseModel):
    text: str
    vector: list[float] = Field(default_factory=list)


class EmbedResponse(BaseModel):
    model: str
    dimension: int
    items: list[EmbedVector] = Field(default_factory=list)
    traceId: str | None = None


# ----------------------------------------------------------------------
# Judgement output (the core L1 schema)
# ----------------------------------------------------------------------


class JudgementOutput(BaseModel):
    """The structured output we ask the LLM to produce.

    This is the schema `instructor` enforces against model output. Fields here
    are exactly what we want from the model and nothing else. Engine-side
    metadata (latencyMs, model, traceId, ...) is added by the chain layer in
    `JudgementResult`, not requested from the model.
    """

    relevanceScore: int = Field(ge=0, le=100)
    isReal: bool
    isRealConfidence: float = Field(ge=0.0, le=1.0)
    importance: ImportanceLevel
    summary: str = Field(max_length=200)
    keywordMentioned: bool
    reasoning: str = Field(max_length=200)
    expandedKeywords: list[str] = Field(default_factory=list)


class JudgementResult(BaseModel):
    """Full response returned to HotPulse.

    Wraps `JudgementOutput` fields with engine metadata. Either a successful
    judgement (all fields filled, partial=False) or a downgraded result with
    partial=True and an errorCode.
    """

    rawDocumentId: str
    layer: JudgementLayer
    model: str
    promptVersion: str

    # Output fields (flattened from JudgementOutput on success)
    relevanceScore: int | None = None
    isReal: bool | None = None
    isRealConfidence: float | None = None
    importance: ImportanceLevel | None = None
    summary: str | None = None
    keywordMentioned: bool | None = None
    reasoning: str | None = None
    expandedKeywords: list[str] = Field(default_factory=list)

    # Engine metadata
    latencyMs: int = 0
    tokenUsage: TokenUsage = Field(default_factory=TokenUsage)
    traceId: str | None = None

    # Downgrade signal
    partial: bool = False
    errorCode: str | None = None
    errorMessage: str | None = None
    rawModelOutput: str | None = None

    @classmethod
    def from_output(
        cls,
        *,
        rawDocumentId: str,
        layer: JudgementLayer,
        model: str,
        promptVersion: str,
        output: JudgementOutput,
        latencyMs: int,
        tokenUsage: TokenUsage,
        traceId: str | None = None,
    ) -> JudgementResult:
        return cls(
            rawDocumentId=rawDocumentId,
            layer=layer,
            model=model,
            promptVersion=promptVersion,
            relevanceScore=output.relevanceScore,
            isReal=output.isReal,
            isRealConfidence=output.isRealConfidence,
            importance=output.importance,
            summary=output.summary,
            keywordMentioned=output.keywordMentioned,
            reasoning=output.reasoning,
            expandedKeywords=output.expandedKeywords,
            latencyMs=latencyMs,
            tokenUsage=tokenUsage,
            traceId=traceId,
            partial=False,
        )

    @classmethod
    def downgrade(
        cls,
        *,
        rawDocumentId: str,
        layer: JudgementLayer,
        model: str,
        promptVersion: str,
        errorCode: str,
        errorMessage: str,
        rawModelOutput: str | None = None,
        traceId: str | None = None,
    ) -> JudgementResult:
        return cls(
            rawDocumentId=rawDocumentId,
            layer=layer,
            model=model,
            promptVersion=promptVersion,
            partial=True,
            errorCode=errorCode,
            errorMessage=errorMessage,
            rawModelOutput=rawModelOutput,
            traceId=traceId,
        )


# ----------------------------------------------------------------------
# Summarize
# ----------------------------------------------------------------------


class SummarizeHotspot(BaseModel):
    id: str
    title: str
    content: str
    source: str
    publishedAt: datetime | None = None


class SummarizeRequest(BaseModel):
    topicId: str
    topicName: str
    hotspots: list[SummarizeHotspot]
    style: SummaryStyle = SummaryStyle.EVENT_DETAIL
    lengthHint: SummaryLengthHint = SummaryLengthHint.SHORT
    forceModel: str | None = None


class SummarizeOutput(BaseModel):
    summary: str
    keyPoints: list[str] = Field(default_factory=list, max_length=8)


class SummarizeResult(BaseModel):
    summary: str
    keyPoints: list[str] = Field(default_factory=list)
    model: str
    promptVersion: str
    latencyMs: int = 0
    tokenUsage: TokenUsage = Field(default_factory=TokenUsage)
    traceId: str | None = None


class JudgeBatchResultItem(BaseModel):
    rawDocumentId: str
    result: JudgementResult


class JudgeBatchResult(BaseModel):
    results: list[JudgeBatchResultItem] = Field(default_factory=list)
    totalLatencyMs: int = 0
    successCount: int = 0
    partialCount: int = 0


class ExpandResult(BaseModel):
    expandedKeywords: list[str] = Field(default_factory=list)
    model: str
    promptVersion: str
    latencyMs: int = 0
    traceId: str | None = None


class AggregateHintResult(BaseModel):
    decision: AggregateHintVerdict
    matchedEventId: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    alternativeMatches: list[str] = Field(default_factory=list)
    model: str
    promptVersion: str
    latencyMs: int = 0
    traceId: str | None = None


class TriageHintAlternative(BaseModel):
    status: TriageStatus
    score: float = Field(ge=0.0, le=1.0)


class TriageHintResult(BaseModel):
    recommendedTriageStatus: TriageStatus
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    alternativeStatuses: list[TriageHintAlternative] = Field(default_factory=list)
    model: str
    promptVersion: str
    latencyMs: int = 0
    traceId: str | None = None


# ----------------------------------------------------------------------
# Health
# ----------------------------------------------------------------------


class HealthCheck(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    model: str
    modelReachable: bool
    esReachable: bool
    langfuseReachable: bool
    defaultLayer: str
    supportedModels: list[str]


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------


class ErrorResponse(BaseModel):
    code: str
    message: str
    layer: JudgementLayer | None = None
    model: str | None = None
    promptVersion: str | None = None
    traceId: str | None = None
