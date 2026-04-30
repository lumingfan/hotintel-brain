"""Consume async Brain judge requests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.chains.l2_rag import run_judge_l2
from src.common.models import JudgementResult, JudgeRequest
from src.mq.messages import BrainJudgeCompletedMessage, BrainJudgeRequestedMessage


class BrainJudgeConsumer:
    def __init__(
        self,
        *,
        publisher,
        judge_runner: Callable[[JudgeRequest], Awaitable[JudgementResult]] = run_judge_l2,
    ) -> None:
        self.publisher = publisher
        self.judge_runner = judge_runner

    async def handle(self, message: BrainJudgeRequestedMessage) -> BrainJudgeCompletedMessage:
        request = message.to_judge_request()
        result = await self.judge_runner(request)
        completed = BrainJudgeCompletedMessage(
            jobId=message.jobId,
            topicId=message.topicId,
            result=result,
        )
        await self.publisher.publish_completed(completed)
        return completed
