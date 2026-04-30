"""Embedding provider for L2 retrieval."""

from __future__ import annotations

import asyncio
from functools import lru_cache

import torch
from sentence_transformers import SentenceTransformer

from src.common.config import get_settings


def resolve_torch_device(preferred: str) -> str:
    value = preferred.strip().lower()
    if value and value != "auto":
        return value
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class EmbeddingProvider:
    """SentenceTransformer-backed embedding provider."""

    def __init__(self, model_path: str, device: str) -> None:
        self.model_path = model_path
        self.device = resolve_torch_device(device)
        self._model = SentenceTransformer(model_path, device=self.device)

    @property
    def model_name(self) -> str:
        return self.model_path

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]

    async def dimension(self) -> int:
        vector = (await self.embed(["dimension probe"]))[0]
        return len(vector)


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    return EmbeddingProvider(
        model_path=settings.brain_embed_model_path,
        device=settings.brain_device,
    )

