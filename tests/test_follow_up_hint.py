"""Follow-up hint endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.common.models import FollowUpHintResult, FollowUpStatus


def _sample_request() -> dict[str, object]:
    return {
        "event": {
            "eventId": "evt_001",
            "topicId": "tp_001",
            "topicName": "AI Coding Models",
            "canonicalTitle": "Claude Code remote MCP support",
            "canonicalSummary": "Anthropic shipped remote MCP support.",
            "sources": ["hackernews", "weibo"],
            "topImportanceLevel": "high",
            "topRelevanceScore": 58,
            "hotspotCount": 2,
            "sourceCount": 2,
            "triageStatus": "REVIEWING",
            "currentFollowUpStatus": "NONE",
            "currentFollowUpNote": "",
        }
    }


def test_follow_up_hint_returns_recommendation(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        "src.api.routes_follow_up_hint.run_follow_up_hint",
        AsyncMock(
            return_value=FollowUpHintResult(
                recommendedFollowUpStatus=FollowUpStatus.NEEDS_FOLLOW_UP,
                suggestedActions=[
                    "Read the official release notes for the shipped capability.",
                    "Check a second community source for early operator feedback.",
                ],
                confidence=0.74,
                reasoning="The event is borderline and still needs one more verification hop.",
                model="gpt-4o-mini",
                promptVersion="follow-up-hint-v1.0",
                latencyMs=88,
                traceId="tr_follow_up",
                fallbackUsed=False,
                fallbackReason=None,
            )
        ),
    )

    response = client.post("/v1/follow-up-hint", json=_sample_request())

    assert response.status_code == 200
    body = response.json()
    assert body["recommendedFollowUpStatus"] == "NEEDS_FOLLOW_UP"
    assert len(body["suggestedActions"]) == 2
    assert body["fallbackUsed"] is False


def test_follow_up_hint_returns_fallback_payload(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        "src.api.routes_follow_up_hint.run_follow_up_hint",
        AsyncMock(
            return_value=FollowUpHintResult(
                recommendedFollowUpStatus=FollowUpStatus.WATCHING,
                suggestedActions=["Keep the event on watch and wait for another strong source."],
                confidence=0.35,
                reasoning="The agent fell back to the conservative path.",
                model="gpt-4o-mini",
                promptVersion="follow-up-hint-v1.0",
                latencyMs=41,
                traceId=None,
                fallbackUsed=True,
                fallbackReason="usage_limit",
            )
        ),
    )

    response = client.post("/v1/follow-up-hint", json=_sample_request())

    assert response.status_code == 200
    body = response.json()
    assert body["fallbackUsed"] is True
    assert body["fallbackReason"] == "usage_limit"
    assert body["recommendedFollowUpStatus"] == "WATCHING"
