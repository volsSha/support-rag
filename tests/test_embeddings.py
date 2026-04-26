from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.rag.embeddings import encode_documents, encode_query, load_embedding_model


def test_load_embedding_model_caches():
    mock_model = MagicMock()
    with patch("src.rag.embeddings.SentenceTransformer", return_value=mock_model) as mock_cls:
        m1 = load_embedding_model("test-model")
        m2 = load_embedding_model("test-model")
        assert m1 is m2
        mock_cls.assert_called_once_with("test-model")


def test_encode_query_with_mock():
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1, 0.2, 0.3]
    result = encode_query("hello", model=mock_model)
    assert result == [0.1, 0.2, 0.3]
    mock_model.encode.assert_called_once_with("hello", normalize_embeddings=True)


def test_encode_documents_with_mock():
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.1, 0.2], [0.3, 0.4]]
    result = encode_documents(["doc1", "doc2"], model=mock_model, batch_size=8)
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    mock_model.encode.assert_called_once_with(["doc1", "doc2"], normalize_embeddings=True, batch_size=8)


@pytest.mark.skipif(
    True,
    reason="Requires downloaded model; run manually with: pip install sentence-transformers",
)
def test_encode_query_real():
    model = load_embedding_model("all-MiniLM-L6-v2")
    result = encode_query("What is support?", model=model)
    assert isinstance(result, list)
    assert len(result) == 384
    assert all(isinstance(x, float) for x in result)


@pytest.mark.skipif(
    True,
    reason="Requires downloaded model; run manually with: pip install sentence-transformers",
)
def test_encode_documents_real():
    model = load_embedding_model("all-MiniLM-L6-v2")
    result = encode_documents(["doc one", "doc two"], model=model)
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(len(v) == 384 for v in result)
