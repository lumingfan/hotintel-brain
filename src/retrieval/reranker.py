"""Cross-encoder reranker for L2 retrieval."""

from __future__ import annotations

import asyncio
from functools import lru_cache

from sentence_transformers import CrossEncoder

from src.common.config import get_settings
from src.retrieval.embeddings import resolve_torch_device
from src.retrieval.types import RetrievalCandidate


class Reranker:
    def __init__(self, model_path: str, device: str) -> None:
        self.model_path = model_path
        self.device = resolve_torch_device(device)
        self._model = CrossEncoder(model_path, device=self.device)

    async def rerank(
        self,
        query_text: str,
        candidates: list[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        if not candidates:
            return []
        return await asyncio.to_thread(self._rerank_sync, query_text, candidates)

    def _rerank_sync(
        self,
        query_text: str,
        candidates: list[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        pairs = [
            (query_text, f"{candidate.title}\n{candidate.summary or ''}\n{candidate.content}")
            for candidate in candidates
        ]
        scores = self._model.predict(pairs)
        ranked = [
            candidate.model_copy(update={"rerank_score": float(score)})
            for candidate, score in zip(candidates, scores, strict=True)
        ]
        return sorted(ranked, key=lambda item: item.rerank_score or 0.0, reverse=True)


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    settings = get_settings()
    return Reranker(
        model_path=settings.brain_rerank_model_path,
        device=settings.brain_device,
    )
