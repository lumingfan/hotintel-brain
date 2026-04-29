"""Route-level upstream error mapping tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.common.config import get_settings
from src.common.models import JudgementLayer, JudgementResult, SummarizeResult
from src.llm.client import UpstreamRateLimitError, UpstreamTimeoutError


def _sample_judge_request() -> dict[str, object]:
    return {
        "rawDocument": {
            "id": "rd_001",
            "title": "Anthropic releases Claude Sonnet 4.6",
            "content": "Anthropic announced Claude Sonnet 4.6.",
            "source": "hackernews",
        },
        "topicContext": {
            "topicId": "tp_001",
            "topicName": "AI Coding Models",
            "primaryKeyword": "Claude Sonnet 4.6",
            "expandedKeywords": ["Claude Sonnet", "Claude Code"],
            "rule": {"minRelevanceScore": 60, "requireDirectKeywordMention": False},
        },
    }


def _sample_summarize_request() -> dict[str, object]:
    return {
        "topicId": "tp_001",
        "topicName": "AI Coding Models",
        "hotspots": [
            {
                "id": "hs_001",
                "title": "Anthropic releases Claude Sonnet 4.6",
                "content": "Anthropic announced Claude Sonnet 4.6.",
                "source": "hackernews",
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


def test_judge_maps_upstream_timeout_to_408(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    async def fake_run_judge(_request):
        raise UpstreamTimeoutError("Timed out")

    monkeypatch.setattr("src.api.routes_judge.run_judge", fake_run_judge)

    response = client.post("/v1/judge", json=_sample_judge_request())

    assert response.status_code == 408
    assert response.json()["detail"]["code"] == "LLM_TIMEOUT"


def test_judge_maps_rate_limit_to_429(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    async def fake_run_judge(_request):
        raise UpstreamRateLimitError("Rate limited")

    monkeypatch.setattr("src.api.routes_judge.run_judge", fake_run_judge)

    response = client.post("/v1/judge", json=_sample_judge_request())

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "RATE_LIMITED"


def test_judge_preserves_partial_schema_downgrade(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    async def fake_run_judge(_request):
        return JudgementResult.downgrade(
            rawDocumentId="rd_001",
            layer=JudgementLayer.L1,
            model="gpt-4o-mini",
            promptVersion="judge-v1.0",
            errorCode="SCHEMA_INVALID",
            errorMessage="schema failed",
            rawModelOutput="{bad json}",
        )

    monkeypatch.setattr("src.api.routes_judge.run_judge", fake_run_judge)

    response = client.post("/v1/judge", json=_sample_judge_request())

    assert response.status_code == 200
    assert response.json()["partial"] is True
    assert response.json()["errorCode"] == "SCHEMA_INVALID"


def test_summarize_maps_upstream_timeout_to_408(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    async def fake_run_summarize(_request):
        raise UpstreamTimeoutError("Timed out")

    monkeypatch.setattr("src.api.routes_summarize.run_summarize", fake_run_summarize)

    response = client.post("/v1/summarize", json=_sample_summarize_request())

    assert response.status_code == 408
    assert response.json()["detail"]["code"] == "LLM_TIMEOUT"


def test_summarize_maps_rate_limit_to_429(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    async def fake_run_summarize(_request):
        raise UpstreamRateLimitError("Rate limited")

    monkeypatch.setattr("src.api.routes_summarize.run_summarize", fake_run_summarize)

    response = client.post("/v1/summarize", json=_sample_summarize_request())

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "RATE_LIMITED"


def test_summarize_success_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    async def fake_run_summarize(_request):
        return SummarizeResult(
            summary="AI Coding Models 近期焦点集中在 Claude Sonnet 4.6 发布。",
            keyPoints=["Claude Sonnet 4.6", "编程能力", "推理提升"],
            model="gpt-4o-mini",
            promptVersion="summarize-v1.0",
            latencyMs=500,
        )

    monkeypatch.setattr("src.api.routes_summarize.run_summarize", fake_run_summarize)

    response = client.post("/v1/summarize", json=_sample_summarize_request())

    assert response.status_code == 200
    assert response.json()["promptVersion"] == "summarize-v1.0"
