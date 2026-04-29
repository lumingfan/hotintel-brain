"""FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from src import __version__
from src.api.routes_health import router as health_router
from src.api.routes_judge import router as judge_router
from src.api.routes_summarize import router as summarize_router
from src.common.config import get_settings
from src.observability.langfuse_client import trace_disabled_warning


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.brain_log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    trace_disabled_warning()

    app = FastAPI(
        title="HotIntel Brain",
        version=__version__,
        description=(
            "LLM-driven hot-intel judgement service for the HotPulse platform. "
            "See `docs/api/contract.md` for the full V1 contract."
        ),
    )
    app.include_router(health_router, prefix="/v1")
    app.include_router(judge_router, prefix="/v1")
    app.include_router(summarize_router, prefix="/v1")
    return app


# Uvicorn entrypoint: `uvicorn src.api.main:app`
app = create_app()
