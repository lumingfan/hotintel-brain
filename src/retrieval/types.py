"""Shared retrieval data structures."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalCandidate(BaseModel):
    doc_id: str
    title: str
    content: str
    summary: str | None = None
    source: str | None = None
    published_at: str | None = None
    bm25_score: float | None = None
    dense_score: float | None = None
    rerank_score: float | None = None


class RetrievalResult(BaseModel):
    items: list[RetrievalCandidate] = Field(default_factory=list)
    context: str = ""
