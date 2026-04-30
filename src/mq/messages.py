"""MQ message schemas for async Brain flows."""

from __future__ import annotations

from pydantic import BaseModel

from src.common.models import JudgementResult, JudgeRequest, RawDocument, TopicContext


class BrainJudgeRequestedMessage(BaseModel):
    jobId: str
    topicId: str
    rawDocument: RawDocument
    topicContext: TopicContext
    forceModel: str | None = None
    routing_key: str = "hotintel.judge.requested"

    def to_judge_request(self) -> JudgeRequest:
        return JudgeRequest(
            rawDocument=self.rawDocument,
            topicContext=self.topicContext,
            forceLayer=None,
            forceModel=self.forceModel,
        )


class BrainJudgeCompletedMessage(BaseModel):
    jobId: str
    topicId: str
    result: JudgementResult
    routing_key: str = "hotintel.judge.completed"
