"""Hybrid retrieval orchestration for L2."""

from __future__ import annotations

from functools import lru_cache

from src.retrieval.embeddings import EmbeddingProvider, get_embedding_provider
from src.retrieval.es_client import EsRetrievalClient, get_es_retrieval_client
from src.retrieval.reranker import Reranker, get_reranker
from src.retrieval.types import RetrievalCandidate, RetrievalResult


class HybridRetriever:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        es_client: EsRetrievalClient,
        reranker: Reranker,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.es_client = es_client
        self.reranker = reranker

    async def retrieve(
        self,
        *,
        topic_id: str,
        query_text: str,
        top_k: int = 5,
    ) -> RetrievalResult:
        query_vector = (await self.embedding_provider.embed([query_text]))[0]
        candidates = await self.es_client.hybrid_search(
            topic_id=topic_id,
            query_text=query_text,
            query_vector=query_vector,
        )
        ranked = await self.reranker.rerank(query_text, candidates)
        trimmed = ranked[:top_k]
        return RetrievalResult(
            items=trimmed,
            context=format_context(trimmed),
        )


def format_context(candidates: list[RetrievalCandidate]) -> str:
    if not candidates:
        return ""
    blocks: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[{index}] doc_id={candidate.doc_id}",
                    f"title: {candidate.title}",
                    f"source: {candidate.source}",
                    f"summary: {candidate.summary}",
                    f"content: {candidate.content}",
                    f"rerank_score: {candidate.rerank_score}",
                ]
            )
        )
    return "\n\n".join(blocks)


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    return HybridRetriever(
        embedding_provider=get_embedding_provider(),
        es_client=get_es_retrieval_client(),
        reranker=get_reranker(),
    )
