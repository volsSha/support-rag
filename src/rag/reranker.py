from src.config import get_settings

_reranker: str | None = None


def load_reranker(model_name: str | None = None) -> str:
    global _reranker
    if _reranker is None:
        settings = get_settings()
        _reranker = model_name or settings.reranker.model_name
    return _reranker


def rerank(
    query: str,
    chunks: list[dict],
    reranker_model: str | None = None,
    top_n: int | None = None,
) -> list[dict]:
    if not chunks:
        return []

    settings = get_settings()
    _ = reranker_model or load_reranker(settings.reranker.model_name)
    keep = top_n or settings.reranker.top_n

    query_terms = set(query.lower().split())

    def score_chunk(content: str) -> float:
        terms = set(content.lower().split())
        if not query_terms or not terms:
            return 0.0
        overlap = len(query_terms & terms)
        return overlap / len(query_terms)

    scores = [score_chunk(chunk["content"]) for chunk in chunks]

    scored = [
        {**chunk, "rerank_score": float(score)}
        for chunk, score in zip(chunks, scores)
    ]
    scored.sort(key=lambda c: c["rerank_score"], reverse=True)

    return scored[:keep]
