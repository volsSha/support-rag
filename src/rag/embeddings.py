from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from src.config import get_settings


class _EmbeddingResult:
    def __init__(self, data: Any):
        self._data = data

    def tolist(self):
        return self._data


class SentenceTransformer:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def encode(
        self,
        texts: str | list[str],
        normalize_embeddings: bool = True,
        batch_size: int | None = None,
    ) -> _EmbeddingResult:
        _ = normalize_embeddings
        _ = batch_size
        dimensions = get_settings().embedding.dimensions
        if isinstance(texts, str):
            return _EmbeddingResult(_hashed_embedding(texts, dimensions))
        return _EmbeddingResult([_hashed_embedding(text, dimensions) for text in texts])


_model: SentenceTransformer | None = None


def _hashed_embedding(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for token in re.split(r'\W+', text.lower()):
        if not token:
            continue
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = (digest[5] / 255.0) + 0.5
        vector[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def load_embedding_model(model_name: str | None = None) -> SentenceTransformer:
    global _model
    if _model is not None:
        return _model
    _model = SentenceTransformer(model_name or get_settings().embedding.model_name)
    return _model


def encode_query(text: str, model: SentenceTransformer | None = None) -> list[float]:
    m = model or _model or load_embedding_model()
    embedding = m.encode(text, normalize_embeddings=True)
    return embedding.tolist() if hasattr(embedding, "tolist") else embedding


def encode_documents(
    texts: list[str],
    model: SentenceTransformer | None = None,
    batch_size: int | None = None,
) -> list[list[float]]:
    m = model or _model or load_embedding_model()
    bs = batch_size or get_settings().embedding.batch_size
    embeddings = m.encode(texts, normalize_embeddings=True, batch_size=bs)
    return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings
