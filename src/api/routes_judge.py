"""POST /v1/judge — L1 judgement entrypoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.chains.l1_singleshot import run_judge
from src.common.models import JudgementResult, JudgeRequest
from src.llm.client import (
    ModelUnavailableError,
    UnsupportedModelError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
)

router = APIRouter()


@router.post("/judge", response_model=JudgementResult)
async def judge(request: JudgeRequest) -> JudgementResult:
    try:
        return await run_judge(request)
    except UnsupportedModelError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_MODEL",
                "message": str(exc),
            },
        ) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "MODEL_UNAVAILABLE",
                "message": str(exc),
            },
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
