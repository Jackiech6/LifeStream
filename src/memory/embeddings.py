"""Embedding model wrapper for Stage 2 RAG indexing.

Provides a small abstraction over the OpenAI embeddings API so that the
rest of the codebase can depend on a simple `EmbeddingModel` interface.
"""

from __future__ import annotations

import logging
import time
from typing import List, Protocol

import numpy as np

from config.settings import Settings
from src.utils.openai_retry import with_429_retry

logger = logging.getLogger(__name__)


class EmbeddingModel(Protocol):
    """Protocol for text embedding models."""

    def embed_texts(self, texts: List[str]) -> np.ndarray:  # pragma: no cover - protocol
        """Convert a list of texts into an array of embeddings."""
        ...


class OpenAIEmbeddingModel:
    """OpenAI-based embedding model wrapper.

    Uses the official `openai` Python client configured via Settings.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.model_name = self.settings.embedding_model_name
        self.batch_size = int(self.settings.embedding_batch_size)
        self.max_retries = int(self.settings.embedding_max_retries)

        try:
            from openai import OpenAI

            if not self.settings.openai_api_key:
                logger.warning("OPENAI_API_KEY not configured; embeddings will fail at runtime.")
            self._client = OpenAI(api_key=self.settings.openai_api_key)
            logger.info("OpenAIEmbeddingModel initialized (model=%s)", self.model_name)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to initialize OpenAI client for embeddings: %s", exc)
            self._client = None

    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed a single batch of texts. Uses 429 retry for rate limits, plus retries for other transient errors."""
        if not self._client:
            raise RuntimeError(
                "OpenAI client not initialized. "
                "Ensure OPENAI_API_KEY is set in the environment."
            )

        def _create() -> np.ndarray:
            logger.debug("Requesting embeddings for batch of size %d", len(texts))
            response = self._client.embeddings.create(
                model=self.model_name,
                input=texts,
            )
            vectors = [item.embedding for item in response.data]
            return np.array(vectors, dtype=float)

        attempt = 0
        delay = 1.0
        while True:
            try:
                return with_429_retry(_create, max_retries=8, log=logger)
            except Exception as exc:
                attempt += 1
                if attempt > self.max_retries:
                    logger.error("Embedding request failed after %d attempts: %s", attempt, exc)
                    raise
                logger.warning(
                    "Embedding request failed (attempt %d/%d): %s; retrying in %.1fs",
                    attempt,
                    self.max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay *= 2.0

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embed a list of texts, handling batching."""
        if not texts:
            return np.empty((0, 0), dtype=float)

        all_vectors: list[np.ndarray] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_vectors = self._embed_batch(batch)
            all_vectors.append(batch_vectors)

        # Concatenate along first axis; assume all batches have same dim
        return np.vstack(all_vectors)


__all__ = ["EmbeddingModel", "OpenAIEmbeddingModel"]

