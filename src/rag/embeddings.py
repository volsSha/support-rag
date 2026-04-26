from __future__ import annotations

from sentence_transformers import SentenceTransformer

from src.config import get_settings

_model: SentenceTransformer | None = None


def load_embedding_model(model_name: str | None = None) -> SentenceTransformer:
    global _model
    if _model is not None:
        return _model
    name = model_name or get_settings().embedding.model_name
    _model = SentenceTransformer(name)
    return _model


def encode_query(text: str, model: SentenceTransformer | None = None) -> list[float]:
    m = model or _model
    if m is None:
        m = load_embedding_model()
    embedding = m.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def encode_documents(
    texts: list[str],
    model: SentenceTransformer | None = None,
    batch_size: int | None = None,
) -> list[list[float]]:
    m = model or _model
    if m is None:
        m = load_embedding_model()
    bs = batch_size or get_settings().embedding.batch_size
    embeddings = m.encode(texts, normalize_embeddings=True, batch_size=bs)
    return embeddings.tolist()
