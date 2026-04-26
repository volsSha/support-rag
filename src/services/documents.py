from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from src.db.models import ChunkEmbedding, Document, DocumentChunk

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def create_document(
    session: AsyncSession,
    title: str,
    content: str,
    source_url: str | None,
    category: str,
) -> Document:
    document = Document(
        title=title,
        content=content,
        source_url=source_url,
        category=category,
    )
    session.add(document)
    await session.flush()
    await session.refresh(document)
    return document


async def get_all_documents(session: AsyncSession) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_document(session: AsyncSession, document_id: int) -> Document | None:
    return await session.get(Document, document_id)


async def delete_document(session: AsyncSession, document_id: int, db_connection=None) -> bool:
    document = await session.get(Document, document_id)
    if document is None:
        return False

    stmt = select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
    result = await session.execute(stmt)
    chunk_ids = [row[0] for row in result.all()]

    if chunk_ids:
        emb_stmt = select(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(chunk_ids))
        embeddings = (await session.execute(emb_stmt)).scalars().all()
        for emb in embeddings:
            await session.delete(emb)

    await session.delete(document)
    await session.commit()
    return True


async def ingest_document(
    session: AsyncSession,
    document_id: int,
    db_connection=None,
) -> int:
    document = await session.get(Document, document_id)
    if document is None:
        return 0

    from src.rag.chunker import chunk_document
    from src.rag.embeddings import encode_documents

    chunks = chunk_document(document.content)
    if not chunks:
        return 0

    texts = [chunk.content for chunk in chunks]
    embeddings = encode_documents(texts)

    count = 0
    for chunk, embedding in zip(chunks, embeddings):
        db_chunk = DocumentChunk(
            document_id=document_id,
            content=chunk.content,
            chunk_index=chunk.chunk_index,
        )
        session.add(db_chunk)
        await session.flush()

        session.add(ChunkEmbedding(chunk_id=db_chunk.id, embedding_json=json.dumps(embedding)))

        count += 1

    await session.commit()
    return count


async def update_document(
    session: AsyncSession,
    document_id: int,
    title: str | None = None,
    content: str | None = None,
    source_url: str | None = None,
    category: str | None = None,
    db_connection=None,
) -> Document | None:
    document = await session.get(Document, document_id)
    if document is None:
        return None

    content_changed = False

    if title is not None:
        document.title = title
    if content is not None:
        content_changed = content != document.content
        document.content = content
    if source_url is not None:
        document.source_url = source_url
    if category is not None:
        document.category = category

    if content_changed:
        stmt = select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
        result = await session.execute(stmt)
        chunk_ids = [row[0] for row in result.all()]

        if chunk_ids:
            emb_stmt = select(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(chunk_ids))
            embeddings = (await session.execute(emb_stmt)).scalars().all()
            for emb in embeddings:
                await session.delete(emb)

        del_stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        old_chunks = (await session.execute(del_stmt)).scalars().all()
        for chunk in old_chunks:
            await session.delete(chunk)

        from src.rag.chunker import chunk_document
        from src.rag.embeddings import encode_documents

        chunks = chunk_document(document.content)
        if chunks:
            texts = [chunk.content for chunk in chunks]
            embeddings = encode_documents(texts)

            for chunk, embedding in zip(chunks, embeddings):
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                )
                session.add(db_chunk)
                await session.flush()

                session.add(ChunkEmbedding(chunk_id=db_chunk.id, embedding_json=json.dumps(embedding)))

    await session.commit()
    await session.refresh(document)
    return document
