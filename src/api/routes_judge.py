"""POST /v1/judge — L1 judgement entrypoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.chains.l1_singleshot import run_judge
from src.chains.l2_rag import run_judge_l2
from src.common.config import get_settings
from src.common.models import JudgementLayer, JudgementResult, JudgeRequest
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
        requested_layer = request.forceLayer or JudgementLayer(get_settings().brain_default_layer)
        if requested_layer is JudgementLayer.L2:
            return await run_judge_l2(request)
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
