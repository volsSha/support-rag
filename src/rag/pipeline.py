from collections.abc import AsyncGenerator
import json
import logging
import math

from sqlalchemy import select

from src.config import get_settings
from src.db.models import ChunkEmbedding, Conversation, Document, DocumentChunk, Message
from src.rag.safety import RAGResult, Source, compute_confidence

logger = logging.getLogger(__name__)


class RAGPipeline:
    def __init__(self, db_connection=None, settings=None) -> None:
        self._db = db_connection
        self._settings = settings or get_settings()

    async def process_query(
        self,
        query: str,
        user_id: int,
        conversation_id: int | None = None,
    ) -> AsyncGenerator[RAGResult | str, None]:
        from src.rag.context import build_context
        from src.rag.embeddings import encode_query
        from src.rag.reranker import rerank
        from src.llm.openrouter import SYSTEM_PROMPT, get_llm_client
        from src.db.engine import async_session_factory

        query_vector = encode_query(query)

        results: list[tuple[int, float]] = []
        if self._db is not None:
            from src.db.vec import search_similar

            results = search_similar(
                self._db, query_vector, top_k=self._settings.reranker.top_k,
            )
        else:
            async with async_session_factory() as session:
                emb_stmt = select(ChunkEmbedding)
                embeddings = (await session.execute(emb_stmt)).scalars().all()

            qnorm = math.sqrt(sum(v * v for v in query_vector)) or 1e-8
            for row in embeddings:
                vector = json.loads(row.embedding_json)
                vnorm = math.sqrt(sum(v * v for v in vector)) or 1e-8
                dot = sum(a * b for a, b in zip(query_vector, vector))
                cosine = dot / (qnorm * vnorm)
                distance = 1.0 - cosine
                results.append((row.chunk_id, distance))

            results.sort(key=lambda x: x[1])
            results = results[: self._settings.reranker.top_k]

        if not results:
            yield RAGResult(
                answer="I couldn't find any relevant information for your question. "
                      "I'm escalating this to a human support agent who can help you.",
                sources=[],
                confidence=0.0,
                escalated=True,
            )
            return

        chunk_ids = [chunk_id for chunk_id, _ in results]
        stmt = (
            select(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.id.in_(chunk_ids))
        )
        async with async_session_factory() as session:
            result_rows = (await session.execute(stmt)).all()
        chunk_map = {chunk.id: (chunk, doc) for chunk, doc in result_rows}

        raw_chunks = []
        for chunk_id, distance in results:
            entry = chunk_map.get(chunk_id)
            if entry is None:
                continue
            chunk, doc = entry
            raw_chunks.append({
                "chunk_id": chunk.id,
                "content": chunk.content,
                "title": doc.title,
                "url": doc.source_url,
                "distance": distance,
            })

        reranked = rerank(query, raw_chunks, top_n=self._settings.reranker.top_n)

        if reranked:
            top_distance = reranked[0].get("distance", 0.0)
            top_score = reranked[0].get("rerank_score", 0.0)
        else:
            top_distance = results[0][1]
            top_score = 0.0

        confidence, escalated = compute_confidence(
            top_score,
            top_distance,
            self._settings.retrieval.similarity_threshold,
        )

        if escalated:
            yield RAGResult(
                answer="Your question may require human review. "
                      "I'm escalating this to a support agent.",
                sources=[],
                confidence=confidence,
                escalated=True,
            )
            return

        chunks_for_context = [
            {"content": c["content"], "title": c["title"], "url": c["url"]}
            for c in reranked
        ]
        context_str = build_context(
            chunks_for_context, max_tokens=self._settings.retrieval.context_max_tokens,
        )

        llm = get_llm_client()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context_str}\n\nQuestion: {query}"},
        ]

        answer_parts: list[str] = []
        async for token in llm.stream_completion(messages):
            answer_parts.append(token)
            yield token

        answer = "".join(answer_parts)

        sources = [
            Source(
                title=c.get("title", ""),
                url=c.get("url"),
                chunk_id=c["chunk_id"],
            )
            for c in reranked
            if c.get("title")
        ]

        async with async_session_factory() as session:
            if conversation_id is None:
                conv = Conversation(
                    user_id=user_id,
                    title=query[:100],
                )
                session.add(conv)
                await session.flush()
                conversation_id = conv.id

            user_msg = Message(
                conversation_id=conversation_id,
                role="user",
                content=query,
            )
            session.add(user_msg)

            assistant_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
                sources_json=json.dumps([s.model_dump() for s in sources]),
            )
            session.add(assistant_msg)
            await session.commit()

        yield RAGResult(
            answer=answer,
            sources=sources,
            confidence=confidence,
            escalated=False,
        )

    async def ingest_document(self, document_id: int) -> int:
        from src.rag.embeddings import encode_documents
        from src.rag import chunker
        from src.db.engine import async_session_factory

        stmt = select(Document).where(Document.id == document_id)
        async with async_session_factory() as session:
            document = (await session.execute(stmt)).scalar_one_or_none()
            if document is None:
                return 0

            chunks = chunker.chunk_document(document.content)
            embeddings = encode_documents([c.content for c in chunks])

            count = 0
            for i, (chunk_data, embedding) in enumerate(zip(chunks, embeddings)):
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    content=chunk_data.content,
                    chunk_index=i,
                )
                session.add(db_chunk)
                await session.flush()

                if self._db is not None:
                    from src.db.vec import insert_embedding

                    insert_embedding(self._db, db_chunk.id, embedding)
                else:
                    session.add(
                        ChunkEmbedding(chunk_id=db_chunk.id, embedding_json=json.dumps(embedding))
                    )
                count += 1

            await session.commit()
            return count

    async def delete_document_vectors(self, chunk_ids: list[int]) -> None:
        if not chunk_ids:
            return

        if self._db is not None:
            from src.db.vec import delete_embeddings

            delete_embeddings(self._db, chunk_ids)
            return

        from src.db.engine import async_session_factory

        async with async_session_factory() as session:
            stmt = select(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(chunk_ids))
            rows = (await session.execute(stmt)).scalars().all()
            for row in rows:
                await session.delete(row)
            await session.commit()


_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
