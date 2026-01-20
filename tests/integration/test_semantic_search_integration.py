"""Integration-style tests for semantic search over indexed summaries."""

import numpy as np

from src.memory.chunking import make_chunks_from_daily_summary
from src.memory.embeddings import EmbeddingModel
from src.search.semantic_search import SearchQuery, semantic_search
from src.models.data_models import DailySummary, TimeBlock, AudioSegment, Participant
from src.memory.vector_store import ScoredResult, VectorStore
from src.memory.index_builder import index_daily_summary


class InMemoryVectorStore(VectorStore):
    """Simple in-memory vector store using cosine similarity, no faiss dependency."""

    def __init__(self) -> None:
        self._vectors = np.zeros((0, 0), dtype=float)
        self._metadatas = []
        self._ids = []

    def upsert(self, vectors, metadatas, ids):
        if self._vectors.size == 0:
            self._vectors = np.asarray(vectors, dtype=float)
        else:
            self._vectors = np.vstack([self._vectors, np.asarray(vectors, dtype=float)])
        self._metadatas.extend(list(metadatas))
        self._ids.extend(list(ids))

    def query(self, vector, top_k=5, filters=None):
        if self._vectors.size == 0:
            return []

        v = np.asarray(vector, dtype=float).reshape(1, -1)
        # Cosine similarity
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True) + 1e-12
        normed = self._vectors / norms
        q_norm = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
        sims = (normed @ q_norm.T).ravel()

        # Build results with metadata and apply simple filters
        scored = []
        for sim, _id, md in zip(sims, self._ids, self._metadatas):
            md = dict(md)
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
            scored.append(ScoredResult(id=_id, score=float(sim), metadata=md))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    def delete(self, ids):
        # Simple filter-based delete
        remaining_vectors = []
        remaining_metas = []
        remaining_ids = []
        for v, md, _id in zip(self._vectors, self._metadatas, self._ids):
            if _id in ids:
                continue
            remaining_vectors.append(v)
            remaining_metas.append(md)
            remaining_ids.append(_id)
        if remaining_vectors:
            self._vectors = np.vstack(remaining_vectors)
        else:
            self._vectors = np.zeros((0, 0), dtype=float)
        self._metadatas = remaining_metas
        self._ids = remaining_ids


class SimpleEmbeddingModel(EmbeddingModel):
    """Embedding model that maps texts into a low-dimensional space based on keywords."""

    def embed_texts(self, texts):
        vectors = []
        for t in texts:
            v = np.zeros(3, dtype=float)
            if "frontend" in t.lower():
                v[0] = 1.0
            if "latency" in t.lower():
                v[1] = 1.0
            if "lunch" in t.lower() or "commute" in t.lower():
                v[2] = 1.0
            vectors.append(v)
        return np.asarray(vectors, dtype=float)


def _build_meeting_summary() -> DailySummary:
    """Create a small DailySummary representing an engineering sync + lunch."""
    meeting_block = TimeBlock(
        start_time="10:00",
        end_time="11:00",
        activity="Engineering sync",
        location="Office",
        transcript_summary="We discussed frontend architecture and deployment strategy.",
        audio_segments=[
            AudioSegment(
                start_time=0.0,
                end_time=300.0,
                speaker_id="Speaker_01",
                transcript_text="Proposed new frontend architecture.",
            ),
            AudioSegment(
                start_time=300.0,
                end_time=600.0,
                speaker_id="Speaker_02",
                transcript_text="Asked about latency and rollout plan.",
            ),
        ],
        participants=[
            Participant(speaker_id="Speaker_01"),
            Participant(speaker_id="Speaker_02"),
        ],
        action_items=["Speaker_01 to prepare architecture RFC."],
    )

    lunch_block = TimeBlock(
        start_time="12:30",
        end_time="13:00",
        activity="Lunch",
        location="Office kitchen",
        transcript_summary="Casual conversation over lunch.",
    )

    return DailySummary(
        date="2026-01-10",
        video_source="/videos/meeting.mp4",
        time_blocks=[meeting_block, lunch_block],
    )


def test_semantic_search_integration_frontend_question():
    """Ask about frontend and expect the engineering sync block to surface."""
    summary = _build_meeting_summary()
    store = InMemoryVectorStore()
    embedder = SimpleEmbeddingModel()

    # Index summary
    index_daily_summary(summary, store=store, embedder=embedder)

    # Run search
    q = SearchQuery(query="What did we discuss about the frontend?", top_k=3)
    results = semantic_search(q, store=store, embedder=embedder)

    assert results
    top = results[0]
    assert "frontend" in top.text.lower() or "engineering sync" in top.text
    assert top.video_id == "/videos/meeting.mp4"
    assert top.date == "2026-01-10"

