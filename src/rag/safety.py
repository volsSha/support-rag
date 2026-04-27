from pydantic import BaseModel


class Source(BaseModel):
    title: str
    url: str | None
    chunk_id: int


class RAGResult(BaseModel):
    answer: str
    sources: list[Source]
    confidence: float
    escalated: bool
    conversation_id: int | None = None


class ThinkEvent(BaseModel):
    stage: str
    message: str
    details: dict | None = None


def compute_confidence(
    top_score: float,
    top_distance: float,
    threshold: float,
) -> tuple[float, bool]:
    distance_confidence = 1.0 - (top_distance / 2.0)
    distance_confidence = max(0.0, min(1.0, distance_confidence))
    reranker_weight = 0.4
    distance_weight = 1.0 - reranker_weight
    confidence = distance_weight * distance_confidence + reranker_weight * top_score
    confidence = max(0.0, min(1.0, confidence))
    is_escalated = top_distance > threshold
    return confidence, is_escalated
