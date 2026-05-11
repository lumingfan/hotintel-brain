"""Triage hint endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.common.models import TokenUsage, TriageHintResult, TriageStatus
from src.llm.client import TriageHintOutput


def test_triage_hint_returns_recommendation(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        "src.api.routes_triage_hint.run_triage_hint",
        AsyncMock(
            return_value=TriageHintResult(
                recommendedTriageStatus=TriageStatus.CONFIRMED,
                confidence=0.82,
                reasoning="Multiple high-confidence sources.",
                alternativeStatuses=[],
                model="gpt-4o-mini",
                promptVersion="triage-hint-v1.0",
                latencyMs=50,
                traceId="tr_triage",
            )
        ),
    )

    response = client.post(
        "/v1/triage-hint",
        json={
            "event": {
                "eventId": "evt_001",
                "topicId": "tp_001",
                "topicName": "AI Coding Models",
                "canonicalTitle": "Claude Code remote MCP support",
                "canonicalSummary": "Anthropic shipped support.",
                "topImportanceLevel": "high",
                "topRelevanceScore": 91,
                "hotspotCount": 4,
                "sourceCount": 3,
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendedTriageStatus"] == "CONFIRMED"


def test_triage_hint_prompt_requires_chinese_reasoning(monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def fake_triage_hint(
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        prompt_definition,
    ):
        captured["system_prompt"] = system_prompt
        return (
            TriageHintOutput(
                recommendedTriageStatus=TriageStatus.REVIEWING,
                confidence=0.72,
                reasoning="建议先人工复核官方来源, 再决定是否确认。",
                alternativeStatuses=[],
            ),
            TokenUsage(promptTokens=10, completionTokens=5, totalTokens=15),
            30,
            None,
        )

    monkeypatch.setattr("src.api.routes_triage_hint.triage_hint", fake_triage_hint)

    client = TestClient(app)
    response = client.post(
        "/v1/triage-hint",
        json={
            "event": {
                "eventId": "evt_002",
                "topicId": "tp_001",
                "topicName": "AI Coding Models",
                "canonicalTitle": "Claude Code remote MCP support",
                "canonicalSummary": "Anthropic shipped support.",
                "topImportanceLevel": "high",
                "topRelevanceScore": 72,
                "hotspotCount": 3,
                "sourceCount": 2,
            }
        },
    )

    assert response.status_code == 200
    assert "中文" in captured["system_prompt"]
