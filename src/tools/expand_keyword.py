"""Keyword expansion helper for the L3 follow-up agent."""

from __future__ import annotations


def expand_keyword_candidates(
    *,
    topic_name: str,
    primary_keyword: str | None,
    canonical_title: str,
    existing_keywords: list[str] | None = None,
    limit: int = 5,
) -> list[str]:
    candidates = [
        primary_keyword or "",
        topic_name,
        canonical_title,
        canonical_title.split(":", maxsplit=1)[0],
        canonical_title.split("-", maxsplit=1)[0].strip(),
        *(existing_keywords or []),
    ]

    deduped: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        normalized = value.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
        if len(deduped) >= limit:
            break
    return deduped
