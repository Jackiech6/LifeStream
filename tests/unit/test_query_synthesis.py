"""Unit tests for query synthesis."""

import pytest
from unittest.mock import patch, MagicMock

from config.settings import Settings
from src.search.semantic_search import SearchResult
from src.search.query_synthesis import synthesize_answer


def test_synthesize_answer_no_results():
    """With no chunks, return message without calling ChatGPT."""
    settings = Settings()
    out = synthesize_answer("any question", [], settings)
    assert "No relevant" in out or "relevant" in out.lower()
    assert "Try" in out or "query" in out.lower()


def test_synthesize_answer_with_results_mocked_openai():
    """With results, exactly one ChatGPT call; returns synthesized answer."""
    settings = Settings()
    settings.openai_api_key = "sk-test"
    results = [
        SearchResult(
            chunk_id="c1",
            score=0.9,
            text="We discussed deploying the API.",
            video_id="v1",
            date="2025-01-20",
            start_time=0.0,
            end_time=300.0,
            speakers=["Speaker_01"],
            metadata={},
        ),
    ]
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "The team discussed deploying the API."

    with patch("openai.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        out = synthesize_answer("What was discussed?", results, settings)

    assert "deploying" in out.lower() or "API" in out
    mock_client.chat.completions.create.assert_called_once()
