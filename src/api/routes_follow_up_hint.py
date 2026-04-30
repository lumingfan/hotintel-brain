"""POST /v1/follow-up-hint — follow-up recommendation entrypoint."""

from __future__ import annotations

from fastapi import APIRouter

from src.chains.l3_agent import run_follow_up_hint
from src.common.models import FollowUpHintRequest, FollowUpHintResult

router = APIRouter()


@router.post("/follow-up-hint", response_model=FollowUpHintResult)
async def follow_up_hint(request: FollowUpHintRequest) -> FollowUpHintResult:
    return await run_follow_up_hint(request)
