"""Minimal metrics for the V1 eval bootstrap."""

from __future__ import annotations

from statistics import mean


def count_successes(results: list[dict[str, object]]) -> int:
    return sum(1 for result in results if result.get("partial") is not True)


def partial_rate(results: list[dict[str, object]]) -> float:
    if not results:
        return 0.0
    partial_count = sum(1 for result in results if result.get("partial") is True)
    return partial_count / len(results)


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * pct)))
    return ordered[index]


def engineering_metrics(results: list[dict[str, object]]) -> dict[str, float | int]:
    latencies = [int(result.get("latencyMs", 0) or 0) for result in results]
    total_tokens = [
        int(((result.get("tokenUsage") or {}).get("totalTokens", 0) if isinstance(result.get("tokenUsage"), dict) else 0) or 0)
        for result in results
    ]

    return {
        "p50_latency_ms": percentile(latencies, 0.5),
        "p95_latency_ms": percentile(latencies, 0.95),
        "avg_total_tokens": round(mean(total_tokens), 2) if total_tokens else 0,
        "max_total_tokens": max(total_tokens) if total_tokens else 0,
    }
