"""Silver baseline metric tests."""

from __future__ import annotations

from eval.silver_metrics import bucket_from_score, compare_with_baseline_hints


def test_bucket_from_score() -> None:
    assert bucket_from_score(20) == "low"
    assert bucket_from_score(40) == "medium"
    assert bucket_from_score(60) == "high"
    assert bucket_from_score(85) == "urgent"


def test_compare_with_baseline_hints() -> None:
    samples = [
        {
            "baselineHints": {
                "isReal": 1,
                "importance": "high",
                "summary": "Claude Sonnet 4.6 released",
                "keywordMentioned": 1,
                "relevanceScore": 82,
            }
        }
    ]
    results = [
        {
            "isReal": True,
            "importance": "high",
            "summary": "Claude Sonnet 4.6 released with coding improvements",
            "keywordMentioned": True,
            "relevanceScore": 88,
        }
    ]

    summary = compare_with_baseline_hints(samples, results)

    assert summary["evaluated_samples"] == 1
    assert summary["is_real_agreement"] == 1.0
    assert summary["importance_agreement"] == 1.0
    assert summary["keyword_mentioned_agreement"] == 1.0
    assert summary["relevance_bucket_agreement"] == 1.0
