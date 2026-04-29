"""GET /v1/health — pre-flight reachability check."""

from __future__ import annotations

from fastapi import APIRouter

from src import __version__
from src.common.config import get_settings
from src.common.models import HealthCheck
from src.llm.client import is_model_reachable, supported_model_names
from src.observability.langfuse_client import is_reachable as langfuse_reachable

router = APIRouter()


@router.get("/health", response_model=HealthCheck)
async def health() -> HealthCheck:
    settings = get_settings()
    model_ok = is_model_reachable(settings.brain_default_model)
    langfuse_ok = langfuse_reachable()
    es_ok = bool(settings.brain_es_url)  # V1 doesn't actually ping ES yet

    overall = "ok" if (model_ok and langfuse_ok) else "degraded"
    return HealthCheck(
        status=overall,
        version=__version__,
        model=settings.brain_default_model,
        modelReachable=model_ok,
        esReachable=es_ok,
        langfuseReachable=langfuse_ok,
        defaultLayer=settings.brain_default_layer,
        supportedModels=supported_model_names(),
    )
