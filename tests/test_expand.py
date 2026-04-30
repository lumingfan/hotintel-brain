"""Expand endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.common.models import ExpandResult


def test_expand_returns_suggested_keywords(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        "src.api.routes_expand.run_expand",
        AsyncMock(
            return_value=ExpandResult(
                expandedKeywords=["Claude CLI", "Anthropic MCP"],
                model="gpt-4o-mini",
                promptVersion="expand-v1.0",
                latencyMs=50,
                traceId="tr_expand",
            )
        ),
    )

    response = client.post(
        "/v1/expand",
        json={
            "topicId": "tp_001",
            "topicName": "AI Coding Models",
            "primaryKeyword": "Claude Code",
            "existingExpandedKeywords": ["Anthropic"],
            "limit": 8,
        },
    )

    assert response.status_code == 200
    assert response.json()["expandedKeywords"] == ["Claude CLI", "Anthropic MCP"]
