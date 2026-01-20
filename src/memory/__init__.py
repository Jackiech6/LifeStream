"""Memory module for Stage 2 RAG and Stage 3 vector storage.

This module provides:
- Chunking: Convert DailySummary into searchable chunks
- Embeddings: Text embedding models
- Vector Stores: FAISS (local) and Pinecone (cloud) implementations
- Store Factory: Smart factory to choose between implementations
- Index Builder: Index summaries into vector stores
"""

from src.memory.chunking import make_chunks_from_daily_summary, Chunk
from src.memory.embeddings import EmbeddingModel, OpenAIEmbeddingModel
from src.memory.vector_store import VectorStore, FaissVectorStore, ScoredResult
from src.memory.index_builder import index_daily_summary
from src.memory.store_factory import create_vector_store, get_vector_store_type

# Import PineconeVectorStore if available
try:
    from src.memory.pinecone_store import PineconeVectorStore
    __all__ = [
        "make_chunks_from_daily_summary",
        "Chunk",
        "EmbeddingModel",
        "OpenAIEmbeddingModel",
        "VectorStore",
        "FaissVectorStore",
        "PineconeVectorStore",
        "ScoredResult",
        "index_daily_summary",
        "create_vector_store",
        "get_vector_store_type",
    ]
except ImportError:
    __all__ = [
        "make_chunks_from_daily_summary",
        "Chunk",
        "EmbeddingModel",
        "OpenAIEmbeddingModel",
        "VectorStore",
        "FaissVectorStore",
        "ScoredResult",
        "index_daily_summary",
        "create_vector_store",
        "get_vector_store_type",
    ]