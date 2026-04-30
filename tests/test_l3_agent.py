"""L3 follow-up agent tests."""

from __future__ import annotations

import asyncio

import pytest
from pydantic_ai.exceptions import UsageLimitExceeded

from src.chains.l3_agent import (
    L3_AGENT_USAGE_LIMITS,
    ToolCallBudget,
    ToolLimitExceededError,
    run_follow_up_hint,
)
from src.common.models import FollowUpHintRequest


def _sample_request() -> FollowUpHintRequest:
    return FollowUpHintRequest.model_validate(
        {
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
    )


def test_l3_agent_usage_limits_match_spec() -> None:
    assert L3_AGENT_USAGE_LIMITS.request_limit == 6
    assert L3_AGENT_USAGE_LIMITS.tool_calls_limit == 6
    assert L3_AGENT_USAGE_LIMITS.total_tokens_limit == 2000


def test_tool_budget_enforces_per_tool_caps() -> None:
    budget = ToolCallBudget()

    budget.consume("search_history")
    budget.consume("search_history")

    with pytest.raises(ToolLimitExceededError):
        budget.consume("search_history")


def test_run_follow_up_hint_falls_back_on_usage_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_execute_agent(*_args, **_kwargs):
        raise UsageLimitExceeded("request_limit exceeded")

    monkeypatch.setattr("src.chains.l3_agent._build_follow_up_agent", lambda **_kwargs: object())
    monkeypatch.setattr("src.chains.l3_agent._execute_agent", fake_execute_agent)

    result = asyncio.run(run_follow_up_hint(_sample_request()))

    assert result.fallbackUsed is True
    assert result.fallbackReason == "usage_limit"
    assert result.suggestedActions


def test_run_follow_up_hint_falls_back_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_execute_agent(*_args, **_kwargs):
        raise RuntimeError("tool crashed")

    monkeypatch.setattr("src.chains.l3_agent._build_follow_up_agent", lambda **_kwargs: object())
    monkeypatch.setattr("src.chains.l3_agent._execute_agent", fake_execute_agent)

    result = asyncio.run(run_follow_up_hint(_sample_request()))

    assert result.fallbackUsed is True
    assert result.fallbackReason == "tool_error"
