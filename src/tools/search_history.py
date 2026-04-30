"""History search helper for the L3 follow-up agent."""

from __future__ import annotations

from collections.abc import MutableMapping

from pydantic import BaseModel, ConfigDict

from src.retrieval.retriever import HybridRetriever, get_retriever
from src.tools.fetch_doc import FetchedDocument


class HistoryDoc(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    doc_id: str
    title: str
    summary: str | None = None
    source: str | None = None
    published_at: str | None = None
    rerank_score: float | None = None


async def search_history_for_topic(
    *,
    topic_id: str,
    query: str,
    top_k: int = 3,
    retriever: HybridRetriever | None = None,
    doc_cache: MutableMapping[str, FetchedDocument] | None = None,
) -> list[HistoryDoc]:
    if not query.strip():
        return []

    result = await (retriever or get_retriever()).retrieve(
        topic_id=topic_id,
        query_text=query,
        top_k=max(1, min(top_k, 5)),
    )

    items: list[HistoryDoc] = []
    for candidate in result.items:
        if doc_cache is not None:
            doc_cache[candidate.doc_id] = FetchedDocument(
                doc_id=candidate.doc_id,
                title=candidate.title,
                content=candidate.content,
                summary=candidate.summary,
                source=candidate.source,
                published_at=candidate.published_at,
            )
        items.append(
            HistoryDoc(
                doc_id=candidate.doc_id,
                title=candidate.title,
                summary=candidate.summary,
                source=candidate.source,
                published_at=candidate.published_at,
                rerank_score=candidate.rerank_score,
            )
        )
    return items
