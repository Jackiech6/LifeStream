"""Unit tests for PineconeVectorStore."""

from unittest.mock import MagicMock, patch, Mock
import numpy as np
import pytest

from src.memory.pinecone_store import PineconeVectorStore
from src.memory.vector_store import ScoredResult
from config.settings import Settings


@pytest.fixture
def mock_pinecone():
    """Create a mocked Pinecone module (v5+ API)."""
    with patch("pinecone.Pinecone") as mock_pinecone_class, \
         patch("pinecone.ServerlessSpec") as mock_serverless_spec:
        # Mock Pinecone client instance
        mock_client = MagicMock()
        mock_pinecone_class.return_value = mock_client
        
        # Mock list_indexes (returns list of index objects with .name attribute)
        mock_index_obj = MagicMock()
        mock_index_obj.name = "test-index"
        mock_client.list_indexes = MagicMock(return_value=[mock_index_obj])
        
        # Mock create_index
        mock_client.create_index = MagicMock()
        
        # Mock Index class
        mock_index = MagicMock()
        mock_client.Index = MagicMock(return_value=mock_index)
        
        yield mock_pinecone_class, mock_client, mock_index, mock_serverless_spec


@pytest.fixture
def settings_with_pinecone():
    """Create settings with Pinecone API key."""
    settings = Settings()
    settings.pinecone_api_key = "test-api-key"
    settings.pinecone_environment = "us-east-1"
    settings.pinecone_index_name = "test-index"
    settings.pinecone_dimension = 1536
    return settings


def test_pinecone_store_initialization(settings_with_pinecone, mock_pinecone):
    """PineconeVectorStore should initialize with correct settings."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    # Return empty list to trigger index creation
    mock_client.list_indexes.return_value = []
    # After creation, return the index
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.side_effect = [[], [mock_index_obj]]

    store = PineconeVectorStore(settings_with_pinecone)

    assert store.index_name == "test-index"
    assert store.dimension == 1536
    mock_pinecone_class.assert_called_once_with(api_key="test-api-key")


def test_pinecone_store_missing_api_key():
    """PineconeVectorStore should raise error if API key not configured."""
    settings = Settings()
    settings.pinecone_api_key = None

    with pytest.raises(ValueError, match="Pinecone API key not configured"):
        PineconeVectorStore(settings)


def test_pinecone_store_existing_index(settings_with_pinecone, mock_pinecone):
    """PineconeVectorStore should use existing index if available."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    # Return index object with matching name
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    store = PineconeVectorStore(settings_with_pinecone)

    assert store.index == mock_index
    mock_client.create_index.assert_not_called()


def test_pinecone_store_create_index(settings_with_pinecone, mock_pinecone):
    """PineconeVectorStore should create index if it doesn't exist."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    # First call returns empty, second call returns the new index
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.side_effect = [[], [mock_index_obj]]

    store = PineconeVectorStore(settings_with_pinecone)

    # Verify create_index was called with correct parameters
    assert mock_client.create_index.called
    call_kwargs = mock_client.create_index.call_args[1]
    assert call_kwargs["name"] == "test-index"
    assert call_kwargs["dimension"] == 1536
    assert call_kwargs["metric"] == "cosine"


def test_upsert_vectors(settings_with_pinecone, mock_pinecone):
    """upsert should successfully insert vectors into Pinecone."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    store = PineconeVectorStore(settings_with_pinecone)

    vectors = np.random.rand(3, 1536).astype(np.float32)
    metadatas = [{"text": f"chunk_{i}", "date": "2026-01-20"} for i in range(3)]
    ids = [f"chunk_{i}" for i in range(3)]

    store.upsert(vectors, metadatas, ids)

    # Verify upsert was called
    assert mock_index.upsert.called
    # Accept both kwargs-style and positional-style invocations
    call_args, call_kwargs = mock_index.upsert.call_args
    vectors_arg = []
    if "vectors" in call_kwargs:
        vectors_arg = call_kwargs["vectors"]
    elif call_args:
        vectors_arg = call_args[0]
    assert len(vectors_arg) == 3  # 3 vectors


def test_upsert_empty_vectors(settings_with_pinecone, mock_pinecone):
    """upsert should handle empty vectors gracefully."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    store = PineconeVectorStore(settings_with_pinecone)

    vectors = np.array([]).reshape(0, 1536)
    store.upsert(vectors, [], [])

    # Should not call upsert for empty vectors
    mock_index.upsert.assert_not_called()


def test_upsert_mismatched_lengths(settings_with_pinecone, mock_pinecone):
    """upsert should raise ValueError for mismatched array lengths."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    store = PineconeVectorStore(settings_with_pinecone)

    vectors = np.random.rand(3, 1536)
    metadatas = [{"text": "chunk_0"}]
    ids = ["chunk_0"]

    with pytest.raises(ValueError, match="must have the same length"):
        store.upsert(vectors, metadatas, ids)


def test_query_vectors(settings_with_pinecone, mock_pinecone):
    """query should return ScoredResult objects from Pinecone."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    # Mock query response
    mock_index.query.return_value = {
        "matches": [
            {
                "id": "chunk_0",
                "score": 0.95,
                "metadata": {"_id": "chunk_0", "text": "test chunk", "date": "2026-01-20"},
            },
            {
                "id": "chunk_1",
                "score": 0.85,
                "metadata": {"_id": "chunk_1", "text": "another chunk", "date": "2026-01-20"},
            },
        ]
    }

    store = PineconeVectorStore(settings_with_pinecone)

    query_vector = np.random.rand(1536)
    results = store.query(query_vector, top_k=2)

    assert len(results) == 2
    assert isinstance(results[0], ScoredResult)
    assert results[0].id == "chunk_0"
    assert results[0].score == 0.95
    assert results[0].metadata["text"] == "test chunk"

    # Verify query was called
    mock_index.query.assert_called_once()
    call_kwargs = mock_index.query.call_args[1]
    assert call_kwargs["top_k"] == 2
    assert call_kwargs["include_metadata"] is True


def test_query_with_filters(settings_with_pinecone, mock_pinecone):
    """query should apply filters when provided."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    mock_index.query.return_value = {"matches": []}

    store = PineconeVectorStore(settings_with_pinecone)

    query_vector = np.random.rand(1536)
    filters = {"date": "2026-01-20", "video_id": {"$in": ["vid1", "vid2"]}}

    store.query(query_vector, top_k=5, filters=filters)

    # Verify filter was passed
    call_kwargs = mock_index.query.call_args[1]
    assert "filter" in call_kwargs
    assert call_kwargs["filter"] is not None


def test_query_empty_results(settings_with_pinecone, mock_pinecone):
    """query should return empty list when no results found."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    mock_index.query.return_value = {"matches": []}

    store = PineconeVectorStore(settings_with_pinecone)

    query_vector = np.random.rand(1536)
    results = store.query(query_vector, top_k=5)

    assert results == []


def test_delete_vectors(settings_with_pinecone, mock_pinecone):
    """delete should remove vectors from Pinecone."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    store = PineconeVectorStore(settings_with_pinecone)

    ids = ["chunk_0", "chunk_1", "chunk_2"]
    store.delete(ids)

    # Verify delete was called
    mock_index.delete.assert_called()
    # Check that all IDs were deleted (may be batched)
    all_calls = mock_index.delete.call_args_list
    deleted_ids = []
    for call in all_calls:
        args, kwargs = call
        if "ids" in kwargs:
            deleted_ids.extend(kwargs.get("ids", []))
        elif args:
            deleted_ids.extend(args[0])
    assert set(deleted_ids) == set(ids)


def test_delete_empty_list(settings_with_pinecone, mock_pinecone):
    """delete should handle empty ID list gracefully."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    store = PineconeVectorStore(settings_with_pinecone)

    store.delete([])

    # Should not call delete for empty list
    mock_index.delete.assert_not_called()


def test_flatten_metadata(settings_with_pinecone, mock_pinecone):
    """_flatten_metadata should flatten nested metadata."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    store = PineconeVectorStore(settings_with_pinecone)

    nested_metadata = {
        "text": "test",
        "nested": {"key": "value"},
        "list": [1, 2, 3],
    }

    flat = store._flatten_metadata(nested_metadata)

    assert flat["text"] == "test"
    assert flat["nested.key"] == "value"
    assert flat["list"] == [1, 2, 3]


def test_convert_filters(settings_with_pinecone, mock_pinecone):
    """_convert_filters should convert filters to Pinecone format."""
    mock_pinecone_class, mock_client, mock_index, mock_serverless = mock_pinecone
    mock_index_obj = MagicMock()
    mock_index_obj.name = "test-index"
    mock_client.list_indexes.return_value = [mock_index_obj]

    store = PineconeVectorStore(settings_with_pinecone)

    filters = {"date": "2026-01-20", "video_id": ["vid1", "vid2"]}
    pinecone_filter = store._convert_filters(filters)

    # Support both legacy flat format and the $and-wrapped format our helper returns
    if "date" in pinecone_filter and "video_id" in pinecone_filter:
        assert pinecone_filter["date"] == "2026-01-20"
        assert pinecone_filter["video_id"]["$in"] == ["vid1", "vid2"]
    else:
        clauses = pinecone_filter.get("$and", [])
        date_clause = next((c for c in clauses if "date" in c), {})
        video_clause = next((c for c in clauses if "video_id" in c), {})
        assert date_clause.get("date") == "2026-01-20"
        assert video_clause.get("video_id", {}).get("$in") == ["vid1", "vid2"]
