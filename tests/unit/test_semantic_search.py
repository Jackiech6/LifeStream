"""Unit tests for semantic_search."""

from typing import List, Dict, Any, Optional

import numpy as np

from src.search.semantic_search import SearchQuery, semantic_search
from src.memory.vector_store import ScoredResult, VectorStore
from src.memory.embeddings import EmbeddingModel


class DummyEmbedder(EmbeddingModel):
    """Simple embedding model for tests that maps words to 1D positions."""

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        # Map based on presence of keywords to keep it deterministic
        vectors = []
        for text in texts:
            if "frontend" in text:
                vectors.append([1.0])
            elif "latency" in text:
                vectors.append([2.0])
            else:
                vectors.append([0.0])
        return np.array(vectors, dtype=float)


class DummyStore(VectorStore):
    """Simple in-memory store that ignores the query vector and returns pre-set results."""

    def __init__(self, results: List[ScoredResult]) -> None:
        self._results = results

    def upsert(self, vectors: np.ndarray, metadatas: List[dict], ids: List[str]) -> None:
        raise NotImplementedError

    def query(
        self,
        vector: np.ndarray,
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> List[ScoredResult]:
        # Apply simple metadata filters, then trim to top_k
        out: List[ScoredResult] = []
        for r in self._results:
            md = r.metadata or {}
            if filters:
                skip = False
                for fk, fv in filters.items():
                    if fk not in md:
                        skip = True
                        break
                    if isinstance(fv, list):
                        if md[fk] not in fv:
                            skip = True
                            break
                    else:
                        if md[fk] != fv:
                            skip = True
                            break
                if skip:
                    continue
            out.append(r)
            if len(out) >= top_k:
                break
        return out

    def delete(self, ids: List[str]) -> None:
        raise NotImplementedError


def test_semantic_search_basic():
    """Basic search should return top_k results with correct metadata."""
    results = [
        ScoredResult(
            id="chunk1",
            score=0.9,
            metadata={
                "text": "Discussed frontend architecture.",
                "video_id": "v1",
                "date": "2026-01-10",
                "start_time": 3600.0,
                "end_time": 3900.0,
                "speakers": ["Speaker_01"],
            },
        ),
        ScoredResult(
            id="chunk2",
            score=0.5,
            metadata={
                "text": "Talked about database performance.",
                "video_id": "v1",
                "date": "2026-01-10",
                "start_time": 4000.0,
                "end_time": 4300.0,
                "speakers": ["Speaker_02"],
            },
        ),
    ]

    store = DummyStore(results)
    embedder = DummyEmbedder()

    q = SearchQuery(query="What about the frontend?", top_k=1)
    out = semantic_search(q, store=store, embedder=embedder)

    assert len(out) == 1
    r = out[0]
    assert r.chunk_id == "chunk1"
    assert "frontend" in r.text or "Discussed" in r.text
    assert r.video_id == "v1"
    assert r.date == "2026-01-10"
    assert r.start_time == 3600.0
    assert r.end_time == 3900.0
    assert r.speakers == ["Speaker_01"]


def test_semantic_search_filters_and_min_score():
    """Filters and min_score should restrict results."""
    results = [
        ScoredResult(
            id="chunk1",
            score=0.9,
            metadata={
                "text": "Frontend discussion",
                "video_id": "v1",
                "date": "2026-01-10",
                "start_time": 0.0,
                "end_time": 10.0,
                "speakers": ["Speaker_01"],
                "source_type": "summary_block",
            },
        ),
        ScoredResult(
            id="chunk2",
            score=0.4,
            metadata={
                "text": "Latency topic",
                "video_id": "v2",
                "date": "2026-01-11",
                "start_time": 0.0,
                "end_time": 10.0,
                "speakers": ["Speaker_02"],
                "source_type": "transcript_block",
            },
        ),
    ]

    store = DummyStore(results)
    embedder = DummyEmbedder()

    q = SearchQuery(
        query="frontend",
        top_k=5,
        min_score=0.5,
        date="2026-01-10",
        video_id="v1",
        source_types=["summary_block"],
        speaker_ids=["Speaker_01"],
    )

    out = semantic_search(q, store=store, embedder=embedder)
    assert len(out) == 1
    r = out[0]
    assert r.chunk_id == "chunk1"
    assert r.metadata["source_type"] == "summary_block"
    assert r.speakers == ["Speaker_01"]

