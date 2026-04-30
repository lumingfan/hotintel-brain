"""Aggregate hint endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.common.models import AggregateHintResult, AggregateHintVerdict


def test_aggregate_hint_returns_merge_decision(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        "src.api.routes_aggregate_hint.run_aggregate_hint",
        AsyncMock(
            return_value=AggregateHintResult(
                decision=AggregateHintVerdict.MERGE_INTO_EXISTING,
                matchedEventId="evt_001",
                confidence=0.91,
                reasoning="Same release event.",
                alternativeMatches=[],
                model="gpt-4o-mini",
                promptVersion="aggregate-hint-v1.0",
                latencyMs=50,
                traceId="tr_agg",
            )
        ),
    )

    response = client.post(
        "/v1/aggregate-hint",
        json={
            "newHotspot": {
                "id": "hs_001",
                "title": "Claude Code remote MCP",
                "content": "Anthropic shipped it.",
                "source": "weibo",
            },
            "candidateEvents": [
                {
                    "eventId": "evt_001",
                    "canonicalTitle": "Claude Code remote MCP support",
                    "canonicalSummary": "Remote MCP support shipped.",
                    "sources": ["hackernews"],
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "MERGE_INTO_EXISTING"
    assert body["matchedEventId"] == "evt_001"
