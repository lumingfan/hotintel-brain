"""Embed endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.common.models import EmbedResponse, EmbedVector


def test_embed_returns_vectors(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(
        "src.api.routes_embed.embed_texts",
        AsyncMock(
            return_value=EmbedResponse(
                model="bge-m3",
                dimension=3,
                items=[EmbedVector(text="Claude Code", vector=[0.1, 0.2, 0.3])],
                traceId="tr_embed",
            )
        ),
    )

    response = client.post("/v1/embed", json={"texts": ["Claude Code"], "topicId": "tp_001"})

    assert response.status_code == 200
    body = response.json()
    assert body["dimension"] == 3
    assert body["items"][0]["vector"] == [0.1, 0.2, 0.3]
