"""Summarize endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.common.config import get_settings
from src.common.models import (
    SummarizeRequest,
    SummarizeResult,
    TokenUsage,
)


def _sample_summarize_request() -> dict[str, object]:
    return {
        "topicId": "tp_001",
        "topicName": "AI Coding Models",
        "hotspots": [
            {
                "id": "hs_001",
                "title": "Anthropic releases Claude Sonnet 4.6",
                "content": "Anthropic announced Claude Sonnet 4.6 with improvements.",
                "source": "hackernews",
                "publishedAt": "2026-04-17T08:00:00Z",
            }
        ],
        "style": "digest",
        "lengthHint": "short",
    }


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    return TestClient(app)


def test_summarize_returns_503_without_model_credentials(client: TestClient) -> None:
    response = client.post("/v1/summarize", json=_sample_summarize_request())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_UNAVAILABLE"


def test_summarize_returns_chain_result(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    async def fake_run_summarize(request: SummarizeRequest) -> SummarizeResult:
        assert request.topicId == "tp_001"
        return SummarizeResult(
            summary="AI Coding Models 近期焦点集中在 Claude Sonnet 4.6 发布。",
            keyPoints=["Claude Sonnet 4.6", "编程能力", "推理提升"],
            model="gpt-4o-mini",
            promptVersion="summarize-v1.0",
            latencyMs=640,
            tokenUsage=TokenUsage(promptTokens=300, completionTokens=80, totalTokens=380),
            traceId="br_sum_test",
        )

    monkeypatch.setattr("src.api.routes_summarize.run_summarize", fake_run_summarize)

    response = client.post("/v1/summarize", json=_sample_summarize_request())

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]
    assert body["model"] == "gpt-4o-mini"
    assert body["promptVersion"] == "summarize-v1.0"
    assert body["traceId"] == "br_sum_test"
