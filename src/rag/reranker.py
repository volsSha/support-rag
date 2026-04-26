from sentence_transformers import CrossEncoder

from src.config import get_settings

_reranker: CrossEncoder | None = None


def load_reranker(model_name: str | None = None) -> CrossEncoder:
    global _reranker
    if _reranker is None:
        settings = get_settings()
        _reranker = CrossEncoder(model_name or settings.reranker.model_name)
    return _reranker


def rerank(
    query: str,
    chunks: list[dict],
    reranker_model: CrossEncoder | None = None,
    top_n: int | None = None,
) -> list[dict]:
    if not chunks:
        return []

    settings = get_settings()
    model = reranker_model or load_reranker(settings.reranker.model_name)
    keep = top_n or settings.reranker.top_n

    pairs = [(query, chunk["content"]) for chunk in chunks]
    scores = model.predict(pairs)

    scored = [
        {**chunk, "rerank_score": float(score)}
        for chunk, score in zip(chunks, scores)
    ]
    scored.sort(key=lambda c: c["rerank_score"], reverse=True)

    return scored[:keep]
