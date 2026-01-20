"""Unit tests for index_daily_summary."""

from unittest.mock import MagicMock

import numpy as np

from src.memory.index_builder import index_daily_summary
from src.models.data_models import DailySummary, TimeBlock


def _simple_summary() -> DailySummary:
    block = TimeBlock(
        start_time="09:00",
        end_time="09:05",
        activity="Test block",
        transcript_summary="Short summary text.",
    )
    return DailySummary(
        date="2026-01-10",
        video_source="/path/to/video.mp4",
        time_blocks=[block],
    )


def test_index_daily_summary_invokes_store_and_embedder():
    """index_daily_summary should call embedder and store with aligned shapes."""
    summary = _simple_summary()

    mock_store = MagicMock()
    mock_embedder = MagicMock()

    # Simulate 2 chunks with 3-dim vectors
    mock_embedder.embed_texts.return_value = np.ones((2, 3), dtype=float)

    index_daily_summary(summary, store=mock_store, embedder=mock_embedder)

    # embedder called once with a list of texts
    mock_embedder.embed_texts.assert_called_once()
    (texts,), _ = mock_embedder.embed_texts.call_args
    assert isinstance(texts, list)
    assert len(texts) >= 1

    # store.upsert called once with matching lengths
    mock_store.upsert.assert_called_once()
    vectors, metadatas, ids = mock_store.upsert.call_args.args
    assert isinstance(vectors, np.ndarray)
    # There should be at least one metadata/id pair, with lengths matching
    assert len(metadatas) == len(ids) > 0

