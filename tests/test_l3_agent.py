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


def test_follow_up_prompt_requires_chinese_output(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    async def fake_execute_agent(*_args, **_kwargs):
        raise UsageLimitExceeded("request_limit exceeded")

    def fake_build_follow_up_agent(*, model_name: str, prompt_text: str):
        captured["prompt_text"] = prompt_text
        return object()

    monkeypatch.setattr("src.chains.l3_agent._build_follow_up_agent", fake_build_follow_up_agent)
    monkeypatch.setattr("src.chains.l3_agent._execute_agent", fake_execute_agent)

    asyncio.run(run_follow_up_hint(_sample_request()))

    assert "中文" in captured["prompt_text"]


def test_run_follow_up_hint_fallback_copy_is_chinese(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_execute_agent(*_args, **_kwargs):
        raise UsageLimitExceeded("request_limit exceeded")

    monkeypatch.setattr("src.chains.l3_agent._build_follow_up_agent", lambda **_kwargs: object())
    monkeypatch.setattr("src.chains.l3_agent._execute_agent", fake_execute_agent)

    result = asyncio.run(run_follow_up_hint(_sample_request()))

    assert result.fallbackUsed is True
    assert any("\u4e00" <= char <= "\u9fff" for char in result.suggestedActions[0])
    assert any("\u4e00" <= char <= "\u9fff" for char in result.reasoning)


def test_run_follow_up_hint_falls_back_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_execute_agent(*_args, **_kwargs):
        raise RuntimeError("tool crashed")

    monkeypatch.setattr("src.chains.l3_agent._build_follow_up_agent", lambda **_kwargs: object())
    monkeypatch.setattr("src.chains.l3_agent._execute_agent", fake_execute_agent)

    result = asyncio.run(run_follow_up_hint(_sample_request()))

    assert result.fallbackUsed is True
    assert result.fallbackReason == "tool_error"
