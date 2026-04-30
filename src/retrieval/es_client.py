"""Elasticsearch retrieval helpers for L2."""

from __future__ import annotations

from functools import lru_cache

from elasticsearch import AsyncElasticsearch

from src.common.config import get_settings
from src.retrieval.types import RetrievalCandidate


class EsRetrievalClient:
    def __init__(self, url: str, index_name: str, username: str = "", password: str = "") -> None:
        if not url:
            raise ValueError("BRAIN_ES_URL is required for L2 retrieval.")
        auth = (username, password) if username and password else None
        self.index_name = index_name
        self._client = AsyncElasticsearch(url, basic_auth=auth)

    async def hybrid_search(
        self,
        *,
        topic_id: str,
        query_text: str,
        query_vector: list[float],
        text_size: int = 15,
        dense_size: int = 15,
    ) -> list[RetrievalCandidate]:
        text_hits = await self._text_search(topic_id=topic_id, query_text=query_text, size=text_size)
        try:
            dense_hits = await self._dense_search(
                topic_id=topic_id,
                query_vector=query_vector,
                size=dense_size,
            )
        except Exception:
            dense_hits = []
        return merge_candidates(text_hits, dense_hits)

    async def _text_search(
        self,
        *,
        topic_id: str,
        query_text: str,
        size: int,
    ) -> list[RetrievalCandidate]:
        response = await self._client.search(
            index=self.index_name,
            size=size,
            query={
                "bool": {
                    "filter": [{"term": {"topicId": topic_id}}],
                    "must": [
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": ["title^3", "summary^2", "content"],
                            }
                        }
                    ],
                }
            },
        )
        return candidates_from_hits(response["hits"]["hits"], score_key="bm25_score")

    async def _dense_search(
        self,
        *,
        topic_id: str,
        query_vector: list[float],
        size: int,
    ) -> list[RetrievalCandidate]:
        response = await self._client.search(
            index=self.index_name,
            size=size,
            query={
                "script_score": {
                    "query": {
                        "bool": {
                            "filter": [{"term": {"topicId": topic_id}}],
                        }
                    },
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                        "params": {"query_vector": query_vector},
                    },
                }
            },
        )
        return candidates_from_hits(response["hits"]["hits"], score_key="dense_score")


def candidates_from_hits(hits: list[dict], score_key: str) -> list[RetrievalCandidate]:
    candidates: list[RetrievalCandidate] = []
    for hit in hits:
        source = hit.get("_source", {})
        payload = dict(
            doc_id=str(source.get("id") or hit.get("_id")),
            title=source.get("title") or "",
            content=source.get("content") or "",
            summary=source.get("summary"),
            source=source.get("source"),
            published_at=source.get("publishedAt"),
        )
        payload[score_key] = float(hit.get("_score", 0.0))
        candidates.append(RetrievalCandidate(**payload))
    return candidates


def merge_candidates(
    text_hits: list[RetrievalCandidate],
    dense_hits: list[RetrievalCandidate],
) -> list[RetrievalCandidate]:
    merged: dict[str, RetrievalCandidate] = {}
    for candidate in text_hits + dense_hits:
        if candidate.doc_id not in merged:
            merged[candidate.doc_id] = candidate
            continue
        current = merged[candidate.doc_id]
        merged[candidate.doc_id] = current.model_copy(
            update={
                "bm25_score": candidate.bm25_score if candidate.bm25_score is not None else current.bm25_score,
                "dense_score": candidate.dense_score if candidate.dense_score is not None else current.dense_score,
            }
        )
    return list(merged.values())


@lru_cache(maxsize=1)
def get_es_retrieval_client() -> EsRetrievalClient:
    settings = get_settings()
    return EsRetrievalClient(
        url=settings.brain_es_url,
        index_name=settings.brain_es_index_name,
        username=settings.brain_es_user,
        password=settings.brain_es_pass,
    )
