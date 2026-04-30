"""L2 retrieval stack tests."""

from __future__ import annotations

from src.retrieval.retriever import HybridRetriever
from src.retrieval.types import RetrievalCandidate


class FakeEmbeddingProvider:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors

    async def embed(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["Claude Code remote MCP"]
        return self.vectors


class FakeEsClient:
    def __init__(self, candidates: list[RetrievalCandidate]) -> None:
        self.candidates = candidates

    async def hybrid_search(
        self,
        *,
        topic_id: str,
        query_text: str,
        query_vector: list[float],
    ) -> list[RetrievalCandidate]:
        assert topic_id == "tp_001"
        assert query_text == "Claude Code remote MCP"
        assert query_vector == [0.1, 0.2]
        return self.candidates


class FakeReranker:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores

    async def rerank(
        self,
        query_text: str,
        candidates: list[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        assert query_text == "Claude Code remote MCP"
        reranked: list[RetrievalCandidate] = []
        for candidate, score in zip(candidates, self.scores, strict=True):
            reranked.append(candidate.model_copy(update={"rerank_score": score}))
        return sorted(reranked, key=lambda item: item.rerank_score or 0.0, reverse=True)


async def test_retriever_returns_ranked_context_from_hybrid_hits() -> None:
    retriever = HybridRetriever(
        embedding_provider=FakeEmbeddingProvider([[0.1, 0.2]]),
        es_client=FakeEsClient(
            [
                RetrievalCandidate(
                    doc_id="hs_2",
                    title="Anthropic ships MCP server updates",
                    content="Remote MCP support is now available.",
                    source="weibo",
                    summary="Remote MCP support landed.",
                ),
                RetrievalCandidate(
                    doc_id="hs_1",
                    title="Claude Code gets remote MCP",
                    content="Claude Code now supports remote MCP servers.",
                    source="hackernews",
                    summary="Claude Code now supports remote MCP.",
                ),
            ]
        ),
        reranker=FakeReranker([0.73, 0.91]),
    )

    result = await retriever.retrieve(
        topic_id="tp_001",
        query_text="Claude Code remote MCP",
        top_k=2,
    )

    assert [item.doc_id for item in result.items] == ["hs_1", "hs_2"]
    assert "Claude Code gets remote MCP" in result.context
    assert "Remote MCP support is now available." in result.context
