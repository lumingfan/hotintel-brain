"""Minimal metrics for the V1 eval bootstrap."""

from __future__ import annotations


def count_successes(results: list[dict[str, object]]) -> int:
    return sum(1 for result in results if result.get("partial") is not True)


def partial_rate(results: list[dict[str, object]]) -> float:
    if not results:
        return 0.0
    partial_count = sum(1 for result in results if result.get("partial") is True)
    return partial_count / len(results)
