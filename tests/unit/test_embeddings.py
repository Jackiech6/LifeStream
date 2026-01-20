"""Unit tests for OpenAIEmbeddingModel."""

from unittest.mock import MagicMock

import numpy as np

from config.settings import Settings
from src.memory.embeddings import OpenAIEmbeddingModel


class DummyEmbeddingItem:
    def __init__(self, embedding):
        self.embedding = embedding


class DummyEmbeddingResponse:
    def __init__(self, vectors):
        self.data = [DummyEmbeddingItem(v) for v in vectors]


def test_embed_texts_basic(monkeypatch):
    """Basic embedding call should return correct shape."""
    settings = Settings()
    model = OpenAIEmbeddingModel(settings)

    # Patch client on the instance
    dummy_client = MagicMock()
    vectors = [[1.0, 0.0], [0.0, 1.0]]
    dummy_client.embeddings.create.return_value = DummyEmbeddingResponse(vectors)
    model._client = dummy_client
    model.model_name = "test-model"
    model.batch_size = 10

    texts = ["hello", "world"]
    arr = model.embed_texts(texts)

    assert isinstance(arr, np.ndarray)
    assert arr.shape == (2, 2)
    dummy_client.embeddings.create.assert_called_once()
    kwargs = dummy_client.embeddings.create.call_args.kwargs
    assert kwargs["model"] == "test-model"
    assert kwargs["input"] == texts


def test_embed_texts_batching(monkeypatch):
    """Embedding should batch requests according to batch_size."""
    settings = Settings()
    model = OpenAIEmbeddingModel(settings)

    dummy_client = MagicMock()

    def _fake_create(model=None, input=None):
        # Return an identity-like embedding: one hot vector per text
        dim = 4
        vecs = []
        for i, _ in enumerate(input):
            v = [0.0] * dim
            v[min(i, dim - 1)] = 1.0
            vecs.append(v)
        return DummyEmbeddingResponse(vecs)

    dummy_client.embeddings.create.side_effect = _fake_create
    model._client = dummy_client
    model.model_name = "batch-model"
    model.batch_size = 2

    texts = ["t0", "t1", "t2", "t3", "t4"]
    arr = model.embed_texts(texts)

    # 5 texts => 3 batches of size 2,2,1
    assert arr.shape[0] == 5
    assert dummy_client.embeddings.create.call_count == 3


