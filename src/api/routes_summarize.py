"""POST /v1/summarize — summarize entrypoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.chains.summarize_singleshot import run_summarize
from src.common.models import SummarizeRequest, SummarizeResult
from src.llm.client import (
    ModelUnavailableError,
    UnsupportedModelError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
)

router = APIRouter()


@router.post("/summarize", response_model=SummarizeResult)
async def summarize(request: SummarizeRequest) -> SummarizeResult:
    try:
        return await run_summarize(request)
    except UnsupportedModelError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_MODEL", "message": str(exc)},
        ) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "MODEL_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except UpstreamTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail={"code": "LLM_TIMEOUT", "message": str(exc)},
        ) from exc
    except UpstreamRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "RATE_LIMITED", "message": str(exc)},
        ) from exc
