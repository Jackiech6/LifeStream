"""Semantic search API for Stage 2.

Takes natural-language queries and returns the most relevant indexed chunks
from the vector store.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any

from pydantic import BaseModel
import numpy as np

from src.memory.embeddings import EmbeddingModel
from src.memory.vector_store import VectorStore, ScoredResult


class SearchQuery(BaseModel):
    """Input to semantic_search."""

    query: str
    top_k: int = 5
    min_score: Optional[float] = None

    # Optional filters
    date: Optional[str] = None
    video_id: Optional[str] = None
    source_types: Optional[List[str]] = None  # e.g. ["summary_block", "action_item"]
    speaker_ids: Optional[List[str]] = None


class SearchResult(BaseModel):
    """Semantic search result."""

    chunk_id: str
    score: float
    text: str
    video_id: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    speakers: List[str] = []
    metadata: Dict[str, Any] = {}


def _build_filters(query: SearchQuery) -> Dict[str, Any]:
    """Build metadata filters for the vector store from the query."""
    filters: Dict[str, Any] = {}
    if query.date:
        filters["date"] = query.date
    if query.video_id:
        filters["video_id"] = query.video_id
    if query.source_types:
        # Vector store filter implementation treats list values as "one-of"
        filters["source_type"] = query.source_types
    return filters


def semantic_search(
    query: SearchQuery,
    store: VectorStore,
    embedder: EmbeddingModel,
) -> List[SearchResult]:
    """Run a semantic search over the indexed chunks."""
    if not query.query.strip():
        return []

    q_vec = embedder.embed_texts([query.query])
    if isinstance(q_vec, list):
        q_vec = np.array(q_vec, dtype=float)

    filters = _build_filters(query)

    # Ask store for more than we need, then post-filter by speakers/min_score
    raw_results: List[ScoredResult] = store.query(
        q_vec[0],
        top_k=max(query.top_k * 2, query.top_k),
        filters=filters or None,
    )

    results: List[SearchResult] = []

    for r in raw_results:
        md = dict(r.metadata or {})
        speakers = md.get("speakers") or md.get("metadata", {}).get("speakers") or []

        # Filter by speaker_ids if requested (post-filter, since speakers is a list)
        if query.speaker_ids:
            speaker_set = set(str(s) for s in speakers)
            if not speaker_set.intersection(set(query.speaker_ids)):
                continue

        if query.min_score is not None and r.score < query.min_score:
            continue

        results.append(
            SearchResult(
                chunk_id=r.id,
                score=r.score,
                text=md.get("text", ""),
                video_id=md.get("video_id"),
                date=md.get("date"),
                start_time=md.get("start_time"),
                end_time=md.get("end_time"),
                speakers=speakers if isinstance(speakers, list) else [],
                metadata=md,
            )
        )

        if len(results) >= query.top_k:
            break

    # Already sorted by score in most VectorStore implementations, but
    # enforce ordering just in case.
    results.sort(key=lambda r: r.score, reverse=True)
    return results


__all__ = ["SearchQuery", "SearchResult", "semantic_search"]

