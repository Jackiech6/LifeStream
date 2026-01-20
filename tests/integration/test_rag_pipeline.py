"""End-to-end RAG pipeline integration tests for Stage 2."""

from tests.integration.test_semantic_search_integration import (  # type: ignore[import]
    InMemoryVectorStore,
    SimpleEmbeddingModel,
    _build_meeting_summary,
)

from src.search.semantic_search import SearchQuery, semantic_search
from src.memory.index_builder import index_daily_summary


def test_rag_pipeline_frontend_question():
    """End-to-end: index summary then answer a frontend-focused question."""
    summary = _build_meeting_summary()
    store = InMemoryVectorStore()
    embedder = SimpleEmbeddingModel()

    index_daily_summary(summary, store=store, embedder=embedder)

    q = SearchQuery(query="What did we discuss about the frontend last week?", top_k=3)
    results = semantic_search(q, store=store, embedder=embedder)

    assert results
    top = results[0]
    # Ensure we surfaced the engineering sync / frontend context
    assert "frontend" in top.text.lower() or "engineering sync" in top.text
    assert top.video_id == "/videos/meeting.mp4"
    assert top.date == "2026-01-10"


def test_rag_pipeline_speaker_specific_query():
    """End-to-end: query constrained to a specific speaker ID."""
    summary = _build_meeting_summary()
    store = InMemoryVectorStore()
    embedder = SimpleEmbeddingModel()

    index_daily_summary(summary, store=store, embedder=embedder)

    # Ask specifically about the second speaker (Speaker_02) discussing latency
    q = SearchQuery(
        query="What did Speaker_02 say about latency?",
        top_k=5,
        speaker_ids=["Speaker_02"],
    )
    results = semantic_search(q, store=store, embedder=embedder)

    assert results
    # All returned chunks should reference Speaker_02 in their speakers list
    for r in results:
        assert "Speaker_02" in r.speakers

