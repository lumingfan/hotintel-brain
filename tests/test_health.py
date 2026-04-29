"""Health endpoint smoke tests.

These tests must pass without any real API keys. They verify that:

1. The FastAPI app boots cleanly.
2. /v1/health returns the documented schema.
3. Reachability flags correctly reflect missing credentials.
4. The supportedModels list matches ADR 0006 (GPT + Claude only).
"""

from __future__ import annotations

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from src.api.main import app
from src.common.config import get_settings
from src.llm.client import supported_model_names


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Force a clean env so tests don't pick up developer .env values.
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "BRAIN_ES_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    return TestClient(app)


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200


def test_health_response_shape(client: TestClient) -> None:
    response = client.get("/v1/health")
    body = response.json()
    expected_keys = {
        "status",
        "version",
        "model",
        "modelReachable",
        "esReachable",
        "langfuseReachable",
        "defaultLayer",
        "supportedModels",
    }
    assert expected_keys <= set(body.keys())


def test_health_reports_degraded_without_keys(client: TestClient) -> None:
    body = client.get("/v1/health").json()
    assert body["status"] == "degraded"
    assert body["modelReachable"] is False
    assert body["langfuseReachable"] is False


def test_health_supported_models_match_adr_0006(client: TestClient) -> None:
    body = client.get("/v1/health").json()
    # ADR 0006 — V1 whitelist must be GPT + Claude families only.
    assert body["supportedModels"] == supported_model_names()
    for name in body["supportedModels"]:
        assert name.startswith(("gpt-", "claude-")), (
            f"Model {name!r} sneaked into V1 whitelist; see ADR 0006."
        )


def test_health_default_layer_is_l1(client: TestClient) -> None:
    body = client.get("/v1/health").json()
    assert body["defaultLayer"] == "L1"


def test_health_default_model_is_in_whitelist(client: TestClient) -> None:
    body = client.get("/v1/health").json()
    assert body["model"] in body["supportedModels"]


@respx.mock
def test_health_promotes_to_ok_when_keys_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    get_settings.cache_clear()

    respx.get("http://localhost:3000/api/public/health").mock(
        return_value=Response(200, json={"status": "ok"})
    )

    body = TestClient(app).get("/v1/health").json()
    assert body["modelReachable"] is True
    assert body["langfuseReachable"] is True
    assert body["status"] == "ok"
