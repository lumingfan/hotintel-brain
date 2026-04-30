"""Judge batch endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.common.models import (
    ImportanceLevel,
    JudgeBatchResult,
    JudgeBatchResultItem,
    JudgementLayer,
    JudgementOutput,
    JudgementResult,
    TokenUsage,
)


def _sample_batch_payload() -> dict[str, object]:
    return {
        "items": [
            {
                "rawDocument": {
                    "id": "rd_001",
                    "title": "Claude Code remote MCP",
                    "content": "Anthropic shipped remote MCP support.",
                    "source": "hackernews",
                },
                "topicContext": {
                    "topicId": "tp_001",
                    "topicName": "AI Coding Models",
                    "primaryKeyword": "Claude Code",
                },
            }
        ],
        "forceLayer": "L2",
        "maxConcurrency": 2,
    }


def test_judge_batch_returns_results(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        "src.api.routes_judge_batch.run_judge_batch",
        AsyncMock(
            return_value=JudgeBatchResult(
                results=[
                    JudgeBatchResultItem(
                        rawDocumentId="rd_001",
                        result=JudgementResult.from_output(
                            rawDocumentId="rd_001",
                            layer=JudgementLayer.L2,
                            model="gpt-4o-mini",
                            promptVersion="judge-v1.0",
                            output=JudgementOutput(
                                relevanceScore=91,
                                isReal=True,
                                isRealConfidence=0.89,
                                importance=ImportanceLevel.HIGH,
                                summary="batch summary",
                                keywordMentioned=True,
                                reasoning="batch reasoning",
                                expandedKeywords=[],
                            ),
                            latencyMs=80,
                            tokenUsage=TokenUsage(totalTokens=120),
                            traceId="tr_batch",
                        ),
                    )
                ],
                totalLatencyMs=88,
                successCount=1,
                partialCount=0,
            )
        ),
    )

    response = client.post("/v1/judge/batch", json=_sample_batch_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["successCount"] == 1
    assert body["results"][0]["result"]["layer"] == "L2"
