"""POST /v1/judge/batch — batch judgement entrypoint."""

from __future__ import annotations

import asyncio
from time import perf_counter

from fastapi import APIRouter

from src.chains.l1_singleshot import run_judge
from src.chains.l2_rag import run_judge_l2
from src.common.models import (
    JudgeBatchRequest,
    JudgeBatchResult,
    JudgeBatchResultItem,
    JudgementLayer,
    JudgeRequest,
)

router = APIRouter()


async def run_judge_batch(request: JudgeBatchRequest) -> JudgeBatchResult:
    started_at = perf_counter()
    semaphore = asyncio.Semaphore(request.maxConcurrency)
    requested_layer = request.forceLayer or JudgementLayer.L1

    async def _judge_one(item) -> JudgeBatchResultItem:
        async with semaphore:
            single_request = JudgeRequest(
                rawDocument=item.rawDocument,
                topicContext=item.topicContext,
                forceLayer=requested_layer,
                forceModel=request.forceModel,
            )
            if requested_layer is JudgementLayer.L2:
                result = await run_judge_l2(single_request)
            else:
                result = await run_judge(single_request)
            return JudgeBatchResultItem(rawDocumentId=item.rawDocument.id, result=result)

    results = await asyncio.gather(*[_judge_one(item) for item in request.items])
    total_latency_ms = int((perf_counter() - started_at) * 1000)
    partial_count = sum(1 for item in results if item.result.partial)
    return JudgeBatchResult(
        results=results,
        totalLatencyMs=total_latency_ms,
        successCount=len(results) - partial_count,
        partialCount=partial_count,
    )


@router.post("/judge/batch", response_model=JudgeBatchResult)
async def judge_batch(request: JudgeBatchRequest) -> JudgeBatchResult:
    return await run_judge_batch(request)
