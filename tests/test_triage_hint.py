"""Triage hint endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.common.models import TriageHintResult, TriageStatus


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
