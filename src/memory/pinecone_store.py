"""Pinecone vector store implementation for Stage 3.

This module provides a Pinecone-backed implementation of the VectorStore protocol,
replacing the local FAISS-based storage with a managed cloud vector database.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any
import numpy as np

from src.memory.vector_store import VectorStore, ScoredResult
from config.settings import Settings

logger = logging.getLogger(__name__)


class PineconeVectorStore:
    """Pinecone-backed vector store implementation.

    This implementation uses Pinecone as the vector database backend, providing
    managed, scalable vector storage and similarity search.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        index_name: Optional[str] = None,
    ) -> None:
        """Initialize PineconeVectorStore.

        Args:
            settings: Application settings. If None, creates default settings.
            index_name: Override index name from settings.

        Raises:
            ImportError: If pinecone library is not installed.
            ValueError: If Pinecone API key is not configured.
            RuntimeError: If index creation/connection fails.
        """
        self.settings = settings or Settings()
        self._check_dependencies()
        self._initialize_client()
        self.index_name = index_name or self.settings.pinecone_index_name
        self.dimension = self.settings.pinecone_dimension
        self._ensure_index()

    def _check_dependencies(self) -> None:
        """Check if pinecone library is available."""
        try:
            import pinecone
            self._pinecone = pinecone
            logger.debug("Pinecone library is available")
        except ImportError as exc:
            raise ImportError(
                "pinecone library is required for PineconeVectorStore. "
                "Install with: pip install pinecone"
            ) from exc

    def _initialize_client(self) -> None:
        """Initialize Pinecone client (v5+ API)."""
        if not self.settings.pinecone_api_key:
            raise ValueError(
                "Pinecone API key not configured. "
                "Set PINECONE_API_KEY in environment or settings."
            )

        try:
            # Pinecone v5+ uses Pinecone() client instead of init()
            self.client = self._pinecone.Pinecone(api_key=self.settings.pinecone_api_key)
            logger.info("Pinecone client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone client: {e}")
            raise RuntimeError(f"Could not initialize Pinecone client: {e}") from e

    def _ensure_index(self) -> None:
        """Ensure Pinecone index exists, create if it doesn't."""
        try:
            # Check if index exists
            existing_indexes = [idx.name for idx in self.client.list_indexes()]
            if self.index_name in existing_indexes:
                logger.info(f"Pinecone index '{self.index_name}' already exists")
                self.index = self.client.Index(self.index_name)
            else:
                logger.info(
                    f"Creating Pinecone index '{self.index_name}' "
                    f"with dimension {self.dimension}"
                )
                # Create index with cosine similarity (default metric)
                # Using serverless spec for cost-effectiveness
                self.client.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",  # Cosine similarity for normalized embeddings
                    spec=self._pinecone.ServerlessSpec(
                        cloud="aws",
                        region=self.settings.pinecone_environment,
                    ),
                )
                # Wait for index to be ready
                import time
                max_wait = 60  # Maximum wait time in seconds
                waited = 0
                while self.index_name not in [idx.name for idx in self.client.list_indexes()]:
                    if waited >= max_wait:
                        raise RuntimeError(f"Index {self.index_name} not ready after {max_wait} seconds")
                    time.sleep(2)
                    waited += 2
                
                self.index = self.client.Index(self.index_name)
                logger.info(f"Pinecone index '{self.index_name}' created successfully")
        except Exception as e:
            logger.error(f"Failed to ensure Pinecone index: {e}")
            raise RuntimeError(f"Could not ensure Pinecone index: {e}") from e

    def upsert(
        self, vectors: np.ndarray, metadatas: List[dict], ids: List[str]
    ) -> None:
        """Insert or update vectors and metadata in Pinecone.

        Args:
            vectors: Array of vectors to upsert (shape: [n, dimension]).
            metadatas: List of metadata dictionaries (one per vector).
            ids: List of unique IDs (one per vector).

        Raises:
            ValueError: If input arrays have mismatched lengths.
        """
        if vectors.size == 0:
            return

        if len(metadatas) != vectors.shape[0] or len(ids) != vectors.shape[0]:
            raise ValueError("vectors, metadatas, and ids must have the same length")

        # Convert numpy array to list of lists for Pinecone
        vectors_list = vectors.tolist()

        # Prepare vectors for Pinecone (list of tuples: (id, vector, metadata))
        vectors_to_upsert = []
        for i, (vector, metadata, _id) in enumerate(zip(vectors_list, metadatas, ids)):
            # Pinecone metadata must be flat (no nested dicts)
            flat_metadata = self._flatten_metadata(metadata)
            # Add ID to metadata for consistency
            flat_metadata["_id"] = _id
            vectors_to_upsert.append((_id, vector, flat_metadata))

        try:
            # Upsert in batches (Pinecone recommends batches of 100)
            batch_size = 100
            for i in range(0, len(vectors_to_upsert), batch_size):
                batch = vectors_to_upsert[i : i + batch_size]
                self.index.upsert(vectors=batch)
                logger.debug(f"Upserted batch {i // batch_size + 1} ({len(batch)} vectors)")

            logger.info(f"Successfully upserted {len(vectors_to_upsert)} vectors to Pinecone")
        except Exception as e:
            logger.error(f"Failed to upsert vectors to Pinecone: {e}")
            raise RuntimeError(f"Pinecone upsert failed: {e}") from e

    def query(
        self,
        vector: np.ndarray,
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> List[ScoredResult]:
        """Query Pinecone for similar vectors.

        Args:
            vector: Query vector (shape: [dimension] or [1, dimension]).
            top_k: Number of results to return.
            filters: Optional metadata filters (Pinecone metadata filter format).

        Returns:
            List of ScoredResult objects, sorted by score (descending).
        """
        if vector.ndim == 1:
            query_vector = vector.tolist()
        elif vector.ndim == 2 and vector.shape[0] == 1:
            query_vector = vector[0].tolist()
        else:
            raise ValueError(f"Expected 1D or 2D vector with shape [dim] or [1, dim], got {vector.shape}")

        # Convert filters to Pinecone format if provided
        pinecone_filter = None
        if filters:
            pinecone_filter = self._convert_filters(filters)

        try:
            # Query Pinecone
            query_response = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                filter=pinecone_filter,
            )

            # Convert Pinecone results to ScoredResult objects
            results: List[ScoredResult] = []
            for match in query_response.get("matches", []):
                # Pinecone returns scores as similarity (higher is better, 0-1 range)
                score = float(match.get("score", 0.0))
                metadata = match.get("metadata", {})
                _id = metadata.pop("_id", match.get("id", ""))

                # Unflatten metadata if needed
                metadata = self._unflatten_metadata(metadata)

                results.append(ScoredResult(id=_id, score=score, metadata=metadata))

            logger.debug(f"Pinecone query returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Failed to query Pinecone: {e}")
            return []

    def delete(self, ids: List[str]) -> None:
        """Delete vectors from Pinecone by ID.

        Args:
            ids: List of IDs to delete.
        """
        if not ids:
            return

        try:
            # Delete in batches
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                batch = ids[i : i + batch_size]
                self.index.delete(ids=batch)
                logger.debug(f"Deleted batch {i // batch_size + 1} ({len(batch)} IDs)")

            logger.info(f"Successfully deleted {len(ids)} vectors from Pinecone")
        except Exception as e:
            logger.error(f"Failed to delete vectors from Pinecone: {e}")
            raise RuntimeError(f"Pinecone delete failed: {e}") from e

    def _flatten_metadata(self, metadata: dict) -> dict:
        """Flatten nested metadata for Pinecone (only supports flat dicts).

        Args:
            metadata: Nested metadata dictionary.

        Returns:
            Flattened metadata dictionary.
        """
        flat = {}
        for key, value in metadata.items():
            # Pinecone supports: str, int, float, bool, list of these
            if isinstance(value, (str, int, float, bool)):
                flat[key] = value
            elif isinstance(value, list):
                # Only keep lists of simple types
                if all(isinstance(v, (str, int, float, bool)) for v in value):
                    flat[key] = value
                else:
                    # Convert complex lists to JSON strings
                    import json
                    flat[f"{key}_json"] = json.dumps(value)
            elif isinstance(value, dict):
                # Flatten nested dicts with dot notation
                for nested_key, nested_value in value.items():
                    flat[f"{key}.{nested_key}"] = nested_value
            else:
                # Convert other types to strings
                flat[key] = str(value)
        return flat

    def _unflatten_metadata(self, metadata: dict) -> dict:
        """Unflatten metadata from Pinecone format.

        Args:
            metadata: Flattened metadata dictionary.

        Returns:
            Unflattened metadata dictionary (best effort).
        """
        result = {}
        for key, value in metadata.items():
            if "." in key:
                # Handle dot-notation keys (nested dicts)
                parts = key.split(".", 1)
                if parts[0] not in result:
                    result[parts[0]] = {}
                result[parts[0]][parts[1]] = value
            elif key.endswith("_json"):
                # Handle JSON-encoded values
                import json
                original_key = key[:-5]  # Remove "_json" suffix
                try:
                    result[original_key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[original_key] = value
            else:
                result[key] = value
        return result

    def _convert_filters(self, filters: dict) -> dict:
        """Convert generic filter dict to Pinecone filter format.

        Args:
            filters: Generic filter dictionary.

        Returns:
            Pinecone filter dictionary.
        """
        # Pinecone uses MongoDB-style query filters
        # Example: {"$and": [{"date": "2026-01-20"}, {"video_id": {"$in": ["vid1", "vid2"]}}]}
        pinecone_filter = {}

        for key, value in filters.items():
            if isinstance(value, list):
                # Convert list to $in operator
                pinecone_filter[key] = {"$in": value}
            else:
                # Direct equality
                pinecone_filter[key] = value

        # If multiple filters, wrap in $and
        if len(pinecone_filter) > 1:
            return {"$and": [{k: v} for k, v in pinecone_filter.items()]}

        return pinecone_filter


__all__ = ["PineconeVectorStore"]
