"""Factory function for creating vector stores.

This module provides a smart factory that automatically chooses between
FAISS (local) and Pinecone (cloud) based on configuration.
"""

import logging
from typing import Optional

from src.memory.vector_store import VectorStore, FaissVectorStore
from config.settings import Settings

logger = logging.getLogger(__name__)


def create_vector_store(
    settings: Optional[Settings] = None,
    force_type: Optional[str] = None,
    index_dir: Optional[str] = None,
    index_name: Optional[str] = None,
) -> VectorStore:
    """Create a vector store instance based on configuration.

    This function intelligently chooses between FAISS and Pinecone:
    - Uses Pinecone if API key is configured (cloud/production)
    - Falls back to FAISS if Pinecone is not available (local development)
    - Can be overridden with force_type parameter

    Args:
        settings: Application settings. If None, creates default settings.
        force_type: Force a specific type ("faiss" or "pinecone"). If None, auto-selects.
        index_dir: Directory for FAISS index (only used if FAISS is selected).
        index_name: Name of the index (used for both FAISS and Pinecone).

    Returns:
        VectorStore instance (either FaissVectorStore or PineconeVectorStore).

    Raises:
        ValueError: If force_type is invalid or required configuration is missing.
        RuntimeError: If the selected store cannot be initialized.
    """
    if settings is None:
        settings = Settings()

    # Determine which store to use
    if force_type:
        store_type = force_type.lower()
        if store_type not in ["faiss", "pinecone", "auto"]:
            raise ValueError(f"Invalid force_type: {force_type}. Must be 'faiss', 'pinecone', or 'auto'")
    else:
        # Use setting if available, otherwise auto-detect
        store_type = settings.vector_store_type.lower() if hasattr(settings, 'vector_store_type') else "auto"
    
    # Handle "auto" selection
    if store_type == "auto":
        if settings.pinecone_api_key:
            store_type = "pinecone"
            logger.info("Auto-selected PineconeVectorStore (API key configured)")
        else:
            # Check if FAISS is available before falling back
            try:
                import faiss
                store_type = "faiss"
                logger.info("Auto-selected FaissVectorStore (no Pinecone API key, FAISS available)")
            except ImportError:
                # If neither is available, prefer Pinecone and let it fail with a clear error
                store_type = "pinecone"
                logger.warning("No Pinecone API key and FAISS not available - will attempt Pinecone (may fail)")

    # Create the appropriate store
    if store_type == "pinecone":
        try:
            from src.memory.pinecone_store import PineconeVectorStore

            if not settings.pinecone_api_key:
                raise ValueError(
                    "Pinecone API key required but not configured. "
                    "Set PINECONE_API_KEY in environment or use FAISS instead."
                )

            logger.info(f"Initializing PineconeVectorStore (index: {index_name or settings.pinecone_index_name})")
            return PineconeVectorStore(settings=settings, index_name=index_name)

        except ImportError as e:
            logger.error(f"Pinecone not available: {e}")
            # Check if Pinecone was explicitly requested
            if force_type == "pinecone" or (hasattr(settings, 'vector_store_type') and settings.vector_store_type.lower() == "pinecone"):
                raise RuntimeError(
                    "Pinecone requested but not installed. "
                    "Install with: pip install pinecone"
                ) from e
            # Fallback to FAISS if auto-selected, but check if FAISS is available first
            logger.warning("Pinecone not available, checking FAISS fallback...")
            try:
                import faiss
                logger.warning("Falling back to FAISS (Pinecone not available)")
                store_type = "faiss"
            except ImportError:
                raise RuntimeError(
                    "Neither Pinecone nor FAISS is available. "
                    "Pinecone import failed: {}. "
                    "FAISS not installed. "
                    "Install with: pip install pinecone OR pip install faiss-cpu"
                ) from e

    if store_type == "faiss":
        try:
            faiss_index_dir = index_dir or getattr(settings, 'vector_store_index_dir', 'memory_index')
            faiss_index_name = index_name or "default"
            logger.info(f"Initializing FaissVectorStore (index_dir: {faiss_index_dir}, index_name: {faiss_index_name})")
            return FaissVectorStore(
                index_dir=faiss_index_dir,
                index_name=faiss_index_name,
            )
        except ImportError as e:
            raise RuntimeError(
                "FAISS not available. "
                "Install with: pip install faiss-cpu"
            ) from e

    # Should never reach here, but just in case
    raise RuntimeError(f"Failed to create vector store (type: {store_type})")


def get_vector_store_type(settings: Optional[Settings] = None) -> str:
    """Get the vector store type that would be used by create_vector_store.

    Args:
        settings: Application settings. If None, creates default settings.

    Returns:
        "faiss" or "pinecone" indicating which store would be created.
    """
    if settings is None:
        settings = Settings()

    # Check explicit setting first
    if hasattr(settings, 'vector_store_type') and settings.vector_store_type.lower() != "auto":
        store_type = settings.vector_store_type.lower()
        if store_type in ["faiss", "pinecone"]:
            return store_type
    
    # Auto-detect based on API key
    if settings.pinecone_api_key:
        return "pinecone"
    return "faiss"


__all__ = ["create_vector_store", "get_vector_store_type"]
