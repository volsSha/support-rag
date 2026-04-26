from dataclasses import dataclass

CHARS_PER_TOKEN = 4


@dataclass
class RetrievedChunk:
    chunk_id: int
    content: str
    document_title: str
    source_url: str | None
    rerank_score: float
    distance: float


def build_context(
    chunks: list[RetrievedChunk],
    max_tokens: int = 3000,
) -> str:
    if not chunks:
        return ""

    max_chars = max_tokens * CHARS_PER_TOKEN
    budget = max_chars

    seen: dict[str, RetrievedChunk] = {}
    for chunk in chunks:
        key = chunk.document_title
        if key in seen:
            if chunk.rerank_score > seen[key].rerank_score:
                seen[key] = chunk
        else:
            seen[key] = chunk

    deduped = sorted(seen.values(), key=lambda c: c.rerank_score, reverse=True)

    parts: list[str] = []
    for chunk in deduped:
        url_line = chunk.source_url or ""
        header = f"### Source: {chunk.document_title}"
        if url_line:
            header += f"\n{url_line}"

        body = f"{header}\n\n{chunk.content}\n\n---"
        if len(body) <= budget:
            parts.append(body)
            budget -= len(body)
        else:
            available = budget - (len(header) + 4)
            if available > 0:
                truncated = chunk.content[:available] + "..."
                parts.append(f"{header}\n\n{truncated}\n\n---")
            break

    return "\n\n".join(parts)
