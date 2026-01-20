#!/usr/bin/env python3
"""Migration script to migrate data from FAISS to Pinecone.

This script reads existing FAISS index and metadata, then migrates
all vectors and metadata to Pinecone.

Usage:
    python scripts/migrate_faiss_to_pinecone.py [--index-dir DIR] [--index-name NAME]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.memory.vector_store import FaissVectorStore
from src.memory.pinecone_store import PineconeVectorStore
from config.settings import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def migrate_faiss_to_pinecone(
    faiss_index_dir: str = "memory_index",
    faiss_index_name: str = "default",
    pinecone_index_name: str | None = None,
    batch_size: int = 100,
) -> None:
    """Migrate vectors from FAISS to Pinecone.

    Args:
        faiss_index_dir: Directory containing FAISS index files.
        faiss_index_name: Name of FAISS index to migrate.
        pinecone_index_name: Name of Pinecone index (uses settings default if None).
        batch_size: Number of vectors to migrate per batch.
    """
    logger.info("Starting FAISS to Pinecone migration")
    logger.info(f"FAISS index: {faiss_index_dir}/{faiss_index_name}")
    logger.info(f"Pinecone index: {pinecone_index_name or 'default'}")

    # Load FAISS store
    try:
        logger.info("Loading FAISS index...")
        faiss_store = FaissVectorStore(
            index_dir=faiss_index_dir,
            index_name=faiss_index_name,
        )
        logger.info("FAISS index loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load FAISS index: {e}")
        raise

    # Check if FAISS has any data
    if not faiss_store._metadatas:
        logger.warning("FAISS index is empty, nothing to migrate")
        return

    logger.info(f"Found {len(faiss_store._metadatas)} vectors in FAISS index")

    # Initialize Pinecone store
    try:
        settings = Settings()
        if pinecone_index_name:
            settings.pinecone_index_name = pinecone_index_name

        logger.info("Initializing Pinecone store...")
        pinecone_store = PineconeVectorStore(settings=settings, index_name=pinecone_index_name)
        logger.info("Pinecone store initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Pinecone store: {e}")
        raise

    # Migrate vectors
    # Note: FAISS doesn't maintain ID->position mapping, so we need to
    # reconstruct vectors from metadata. This is a limitation of the current
    # FAISS implementation.
    logger.warning(
        "Note: FAISS implementation doesn't maintain ID->vector mapping. "
        "This migration will only migrate metadata. "
        "For full migration, re-index from source data."
    )

    # Get all metadata
    all_metadatas = list(faiss_store._metadatas.values())
    all_ids = [md.get("id") for md in all_metadatas if md.get("id")]

    if not all_ids:
        logger.warning("No valid IDs found in FAISS metadata")
        return

    logger.info(f"Found {len(all_ids)} entries to migrate")

    # Since we can't get vectors from FAISS by ID, we'll need to re-embed
    # This requires the embedding model
    try:
        from src.memory.embeddings import OpenAIEmbeddingModel

        embedder = OpenAIEmbeddingModel(settings)
        logger.info("Embedding model initialized")
    except Exception as e:
        logger.error(f"Failed to initialize embedding model: {e}")
        logger.error("Cannot migrate vectors without embedding model")
        raise

    # Extract texts from metadata and re-embed
    texts = []
    valid_metadatas = []
    valid_ids = []

    for md in all_metadatas:
        _id = md.get("id")
        if not _id:
            continue

        # Try to get text from metadata
        text = md.get("text") or md.get("transcript") or ""
        if not text:
            logger.warning(f"Skipping {_id}: no text found in metadata")
            continue

        texts.append(text)
        valid_metadatas.append(md)
        valid_ids.append(_id)

    if not texts:
        logger.warning("No texts found in metadata, cannot migrate")
        return

    logger.info(f"Re-embedding {len(texts)} texts...")

    # Embed in batches
    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_vectors = embedder.embed_texts(batch_texts)
        all_vectors.append(batch_vectors)
        logger.info(f"Embedded batch {i // batch_size + 1} ({len(batch_texts)} texts)")

    # Concatenate all vectors
    import numpy as np

    vectors = np.vstack(all_vectors)
    logger.info(f"Generated {vectors.shape[0]} vectors with dimension {vectors.shape[1]}")

    # Upsert to Pinecone
    logger.info("Upserting vectors to Pinecone...")
    pinecone_store.upsert(vectors, valid_metadatas, valid_ids)

    logger.info("Migration completed successfully!")
    logger.info(f"Migrated {len(valid_ids)} vectors from FAISS to Pinecone")


def main():
    """Main entry point for migration script."""
    parser = argparse.ArgumentParser(description="Migrate FAISS index to Pinecone")
    parser.add_argument(
        "--index-dir",
        type=str,
        default="memory_index",
        help="Directory containing FAISS index files (default: memory_index)",
    )
    parser.add_argument(
        "--index-name",
        type=str,
        default="default",
        help="Name of FAISS index to migrate (default: default)",
    )
    parser.add_argument(
        "--pinecone-index",
        type=str,
        default=None,
        help="Name of Pinecone index (uses settings default if not specified)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for migration (default: 100)",
    )

    args = parser.parse_args()

    try:
        migrate_faiss_to_pinecone(
            faiss_index_dir=args.index_dir,
            faiss_index_name=args.index_name,
            pinecone_index_name=args.pinecone_index,
            batch_size=args.batch_size,
        )
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
