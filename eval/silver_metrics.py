"""Low-cost silver-label sanity metrics based on HotPulse baseline hints."""

from __future__ import annotations

from difflib import SequenceMatcher
from statistics import mean
from typing import Any


def bucket_from_score(score: int | None) -> str | None:
    if score is None:
        return None
    if score < 40:
        return "low"
    if score < 60:
        return "medium"
    if score < 80:
        return "high"
    return "urgent"


def _agreement(
    samples: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    hint_key: str,
    result_key: str,
    transform_hint=lambda value: value,
    transform_result=lambda value: value,
) -> tuple[int, int]:
    matches = 0
    total = 0
    for sample, result in zip(samples, results, strict=False):
        hint = transform_hint(sample.get("baselineHints", {}).get(hint_key))
        if hint is None:
            continue
        value = transform_result(result.get(result_key))
        total += 1
        if hint == value:
            matches += 1
    return matches, total


def compare_with_baseline_hints(
    samples: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, float | int]:
    is_real_matches, is_real_total = _agreement(
        samples,
        results,
        hint_key="isReal",
        result_key="isReal",
        transform_hint=lambda value: None if value is None else bool(value),
        transform_result=lambda value: None if value is None else bool(value),
    )
    importance_matches, importance_total = _agreement(
        samples,
        results,
        hint_key="importance",
        result_key="importance",
    )
    keyword_matches, keyword_total = _agreement(
        samples,
        results,
        hint_key="keywordMentioned",
        result_key="keywordMentioned",
        transform_hint=lambda value: None if value is None else bool(value),
        transform_result=lambda value: None if value is None else bool(value),
    )
    relevance_matches, relevance_total = _agreement(
        samples,
        results,
        hint_key="relevanceScore",
        result_key="relevanceScore",
        transform_hint=bucket_from_score,
        transform_result=bucket_from_score,
    )

    summary_scores = []
    for sample, result in zip(samples, results, strict=False):
        hint_summary = sample.get("baselineHints", {}).get("summary") or ""
        predicted_summary = result.get("summary") or ""
        if not hint_summary:
            continue
        summary_scores.append(SequenceMatcher(None, hint_summary, predicted_summary).ratio())

    def _rate(matches: int, total: int) -> float:
        return round(matches / total, 4) if total else 0.0

    return {
        "evaluated_samples": len(samples),
        "is_real_agreement": _rate(is_real_matches, is_real_total),
        "is_real_coverage": is_real_total,
        "importance_agreement": _rate(importance_matches, importance_total),
        "importance_coverage": importance_total,
        "keyword_mentioned_agreement": _rate(keyword_matches, keyword_total),
        "keyword_mentioned_coverage": keyword_total,
        "relevance_bucket_agreement": _rate(relevance_matches, relevance_total),
        "relevance_bucket_coverage": relevance_total,
        "summary_similarity": round(mean(summary_scores), 4) if summary_scores else 0.0,
        "summary_coverage": len(summary_scores),
    }
