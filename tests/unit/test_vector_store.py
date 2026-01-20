"""Unit tests for FaissVectorStore."""

from pathlib import Path

import numpy as np

from src.memory.vector_store import FaissVectorStore


def test_upsert_and_query_basic(tmp_path):
    """Basic upsert and query behavior."""
    try:
        store_dir = tmp_path / "index"
        store = FaissVectorStore(index_dir=store_dir, index_name="test")
    except ImportError:
        # faiss may not be installed in all environments; skip gracefully
        return

    vectors = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=float)
    metadatas = [
        {"video_id": "v1", "date": "2026-01-10"},
        {"video_id": "v2", "date": "2026-01-11"},
        {"video_id": "v3", "date": "2026-01-12"},
    ]
    ids = ["a", "b", "c"]

    store.upsert(vectors, metadatas, ids)

    # Query near [1,0] should return at least one result
    q = np.array([1.0, 0.0], dtype=float)
    results = store.query(q, top_k=2)

    assert len(results) > 0
    # All result IDs must come from our inserted set
    assert all(r.id in ids for r in results)


def test_filters_and_delete(tmp_path):
    """Filters and delete should affect returned results."""
    try:
        store_dir = tmp_path / "index"
        store = FaissVectorStore(index_dir=store_dir, index_name="test2")
    except ImportError:
        # faiss may not be installed in all environments; skip gracefully
        return

    vectors = np.array([[1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=float)
    metadatas = [
        {"video_id": "va", "date": "2026-01-10"},
        {"video_id": "vb", "date": "2026-01-11"},
        {"video_id": "vb", "date": "2026-01-11"},
    ]
    ids = ["id1", "id2", "id3"]

    store.upsert(vectors, metadatas, ids)

    q = np.array([1.0, 1.0], dtype=float)

    # Filter by video_id vb
    filtered = store.query(q, top_k=5, filters={"video_id": "vb"})
    assert all(r.metadata.get("video_id") == "vb" for r in filtered)

    # Delete one ID and ensure it no longer appears
    store.delete(["id2"])
    filtered_after_delete = store.query(q, top_k=5, filters={"video_id": "vb"})
    assert all(r.id != "id2" for r in filtered_after_delete)

