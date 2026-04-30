"""Local follow-up scoring helper for one fetched document."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from src.tools.fetch_doc import FetchedDocument


class FollowUpSubScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    suggested_action: str


def score_document_for_follow_up(
    *,
    doc: FetchedDocument,
    context: str,
    event_title: str,
    existing_sources: list[str] | None = None,
) -> FollowUpSubScore:
    haystack = " ".join(
        [
            doc.title,
            doc.summary or "",
            doc.content,
            context,
        ]
    ).lower()
    title_terms = {
        token.lower()
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9.+-]*", event_title)
        if len(token) >= 4
    }

    score = 0.2
    reasons: list[str] = []

    if doc.source and existing_sources and doc.source not in {item.lower() for item in existing_sources}:
        score += 0.2
        reasons.append("adds a new source")
    if any(term in haystack for term in title_terms):
        score += 0.2
        reasons.append("matches the event title directly")
    if any(marker in haystack for marker in ("official", "release", "announced", "documentation", "roadmap", "api")):
        score += 0.2
        reasons.append("contains likely verification signals")
    if len(doc.content) >= 240:
        score += 0.1
        reasons.append("has enough detail to support manual follow-up")

    normalized_score = round(min(score, 0.95), 2)
    if normalized_score >= 0.65:
        action = "Use this document to verify the event before deciding whether to escalate the follow-up."
    else:
        action = "Keep this as supporting context and wait for a stronger confirming signal."

    return FollowUpSubScore(
        score=normalized_score,
        reason="; ".join(reasons) if reasons else "Provides only limited incremental evidence.",
        suggested_action=action,
    )
