"""Index builder: convert DailySummary into vector store entries."""

from __future__ import annotations

from typing import List

import numpy as np

from src.models.data_models import DailySummary
from src.memory.chunking import make_chunks_from_daily_summary
from src.memory.embeddings import EmbeddingModel
from src.memory.vector_store import VectorStore


def index_daily_summary(
    summary: DailySummary,
    store: VectorStore,
    embedder: EmbeddingModel,
) -> None:
    """Index a DailySummary into the given vector store.

    This function is intentionally simple and stateless: it derives chunks from
    the summary, embeds their text, and upserts them into the store with full
    metadata and IDs.
    """
    chunks = make_chunks_from_daily_summary(summary)
    if not chunks:
        return

    texts: List[str] = [c.text for c in chunks]
    vectors = embedder.embed_texts(texts)
    if isinstance(vectors, list):
        vectors = np.array(vectors, dtype=float)

    metadatas = [c.to_metadata_dict() for c in chunks]
    ids = [c.chunk_id for c in chunks]

    store.upsert(vectors, metadatas, ids)


__all__ = ["index_daily_summary"]

