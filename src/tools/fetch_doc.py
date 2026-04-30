"""Fetch a retrieved document from the in-run cache."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict


class FetchedDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    doc_id: str
    title: str
    content: str
    summary: str | None = None
    source: str | None = None
    published_at: str | None = None


async def fetch_document_by_id(
    doc_id: str,
    *,
    cache: Mapping[str, FetchedDocument] | None = None,
) -> FetchedDocument | None:
    if cache is None:
        return None
    return cache.get(doc_id)
