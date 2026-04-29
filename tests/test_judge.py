"""Judge endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.chains.l1_singleshot import run_judge
from src.common.config import get_settings
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
from src.llm.client import StructuredOutputError


def _sample_judge_request() -> dict[str, object]:
    return {
        "rawDocument": {
            "id": "rd_001",
            "title": "Anthropic releases Claude Sonnet 4.6",
            "content": "Anthropic announced Claude Sonnet 4.6.",
            "source": "hackernews",
            "publishedAt": "2026-04-17T08:00:00Z",
            "author": "anthropic",
            "url": "https://example.com",
        },
        "topicContext": {
            "topicId": "tp_001",
            "topicName": "AI Coding Models",
            "primaryKeyword": "Claude Sonnet 4.6",
            "expandedKeywords": ["Claude Sonnet", "Claude Code"],
            "rule": {
                "minRelevanceScore": 60,
                "requireDirectKeywordMention": False,
            },
        },
    }


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    return TestClient(app)


def test_judge_returns_503_without_model_credentials(client: TestClient) -> None:
    response = client.post("/v1/judge", json=_sample_judge_request())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_UNAVAILABLE"


def test_judge_returns_chain_result(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    async def fake_run_judge(request: JudgeRequest) -> JudgementResult:
        assert request.rawDocument.id == "rd_001"
        output = JudgementOutput(
            relevanceScore=92,
            isReal=True,
            isRealConfidence=0.88,
            importance=ImportanceLevel.HIGH,
            summary="Anthropic 发布 Claude Sonnet 4.6。",
            keywordMentioned=True,
            reasoning="Keyword directly mentioned.",
            expandedKeywords=["Anthropic Sonnet"],
        )
        return JudgementResult.from_output(
            rawDocumentId=request.rawDocument.id,
            layer=JudgementLayer.L1,
            model="gpt-4o-mini",
            promptVersion="judge-v1.0",
            output=output,
            latencyMs=820,
            tokenUsage=TokenUsage(promptTokens=612, completionTokens=180, totalTokens=792),
            traceId="br_test",
        )

    monkeypatch.setattr("src.api.routes_judge.run_judge", fake_run_judge)

    response = client.post("/v1/judge", json=_sample_judge_request())

    assert response.status_code == 200
    body = response.json()
    assert body["rawDocumentId"] == "rd_001"
    assert body["model"] == "gpt-4o-mini"
    assert body["promptVersion"] == "judge-v1.0"
    assert body["partial"] is False


@pytest.mark.asyncio
async def test_run_judge_wraps_llm_output(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_judge_document(
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        prompt_definition,
    ) -> tuple[JudgementOutput, TokenUsage, int, str | None]:
        assert model_name == "gpt-4o-mini"
        assert "HotIntel Brain" in system_prompt
        assert "Claude Sonnet 4.6" in user_prompt
        assert prompt_definition.name == "judge"
        return (
            JudgementOutput(
                relevanceScore=92,
                isReal=True,
                isRealConfidence=0.88,
                importance=ImportanceLevel.HIGH,
                summary="Anthropic 发布 Claude Sonnet 4.6。",
                keywordMentioned=True,
                reasoning="Keyword directly mentioned.",
                expandedKeywords=["Anthropic Sonnet"],
            ),
            TokenUsage(promptTokens=612, completionTokens=180, totalTokens=792),
            820,
            "br_test",
        )

    monkeypatch.setattr("src.chains.l1_singleshot.judge_document", fake_judge_document)

    request = JudgeRequest.model_validate(_sample_judge_request())
    result = await run_judge(request)

    assert result.rawDocumentId == "rd_001"
    assert result.model == "gpt-4o-mini"
    assert result.promptVersion == "judge-v1.0"
    assert result.partial is False
    assert result.summary == "Anthropic 发布 Claude Sonnet 4.6。"


@pytest.mark.asyncio
async def test_run_judge_downgrades_schema_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_judge_document(
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        prompt_definition,
    ) -> tuple[JudgementOutput, TokenUsage, int, str | None]:
        raise StructuredOutputError(
            "Output failed schema validation after instructor retry",
            raw_model_output="{bad json}",
        )

    monkeypatch.setattr("src.chains.l1_singleshot.judge_document", fake_judge_document)

    request = JudgeRequest.model_validate(_sample_judge_request())
    result = await run_judge(request)

    assert result.partial is True
    assert result.errorCode == "SCHEMA_INVALID"
    assert result.rawModelOutput == "{bad json}"
