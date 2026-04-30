"""Brain MQ flow tests."""

from __future__ import annotations

from src.common.models import (
    ImportanceLevel,
    JudgementLayer,
    JudgementOutput,
    JudgementResult,
    JudgeRequest,
    RawDocument,
    TokenUsage,
    TopicContext,
)
from src.mq.consumer import BrainJudgeConsumer
from src.mq.messages import BrainJudgeRequestedMessage


class FakePublisher:
    def __init__(self) -> None:
        self.messages = []

    async def publish_completed(self, message) -> None:
        self.messages.append(message)


async def fake_judge_runner(request: JudgeRequest) -> JudgementResult:
    return JudgementResult.from_output(
        rawDocumentId=request.rawDocument.id,
        layer=JudgementLayer.L2,
        model="gpt-4o-mini",
        promptVersion="judge-v1.0",
        output=JudgementOutput(
            relevanceScore=93,
            isReal=True,
            isRealConfidence=0.91,
            importance=ImportanceLevel.HIGH,
            summary="mq summary",
            keywordMentioned=True,
            reasoning="mq reasoning",
            expandedKeywords=["Anthropic MCP"],
        ),
        latencyMs=100,
        tokenUsage=TokenUsage(totalTokens=123),
        traceId="tr_mq",
    )


async def test_brain_consumer_processes_request_and_publishes_completed() -> None:
    publisher = FakePublisher()
    consumer = BrainJudgeConsumer(
        publisher=publisher,
        judge_runner=fake_judge_runner,
    )
    await consumer.handle(
        BrainJudgeRequestedMessage(
            jobId="job_001",
            hotspotId="hs_001",
            rawDocumentId="rd_001",
            topicId="tp_001",
            rawDocument=RawDocument(
                id="rd_001",
                title="Claude Code remote MCP",
                content="Anthropic shipped support.",
                source="hackernews",
            ),
            topicContext=TopicContext(
                topicId="tp_001",
                topicName="AI Coding Models",
                primaryKeyword="Claude Code",
            ),
        )
    )

    assert len(publisher.messages) == 1
    completed = publisher.messages[0]
    assert completed.jobId == "job_001"
    assert completed.hotspotId == "hs_001"
    assert completed.rawDocumentId == "rd_001"
    assert completed.routing_key == "hotintel.judge.completed"
    assert completed.result.summary == "mq summary"
