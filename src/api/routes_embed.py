"""POST /v1/embed — embedding entrypoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.common.models import EmbedRequest, EmbedResponse, EmbedVector
from src.retrieval.embeddings import get_embedding_provider

router = APIRouter()


async def embed_texts(request: EmbedRequest) -> EmbedResponse:
    provider = get_embedding_provider()
    vectors = await provider.embed(request.texts)
    items = [
        EmbedVector(text=text, vector=vector)
        for text, vector in zip(request.texts, vectors, strict=True)
    ]
    dimension = len(items[0].vector) if items else 0
    return EmbedResponse(
        model=provider.model_name,
        dimension=dimension,
        items=items,
    )


@router.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest) -> EmbedResponse:
    try:
        return await embed_texts(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "EMBEDDING_UNAVAILABLE", "message": str(exc)},
        ) from exc
