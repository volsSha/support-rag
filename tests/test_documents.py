import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Document
from src.services.documents import create_document, delete_document, get_all_documents, get_document


async def test_create_document(async_session: AsyncSession):
    doc = await create_document(
        session=async_session,
        title="Test Document",
        content="This is the content of the test document.",
        source_url="https://example.com",
        category="FAQ",
    )

    assert doc.id is not None
    assert doc.title == "Test Document"
    assert doc.content == "This is the content of the test document."
    assert doc.source_url == "https://example.com"
    assert doc.category == "FAQ"
    assert doc.created_at is not None

    result = await async_session.get(Document, doc.id)
    assert result is not None
    assert result.title == "Test Document"


async def test_get_all_documents(async_session: AsyncSession):
    await create_document(async_session, "Doc 1", "Content 1", None, "FAQ")
    await create_document(async_session, "Doc 2", "Content 2", None, "Guide")
    await async_session.commit()

    docs = await get_all_documents(async_session)
    assert len(docs) == 2
    titles = {d.title for d in docs}
    assert titles == {"Doc 1", "Doc 2"}


async def test_get_all_documents_empty(async_session: AsyncSession):
    docs = await get_all_documents(async_session)
    assert docs == []


async def test_get_document(async_session: AsyncSession):
    created = await create_document(async_session, "Find Me", "Some content", None, "Other")
    await async_session.commit()

    found = await get_document(async_session, created.id)
    assert found is not None
    assert found.title == "Find Me"
    assert found.content == "Some content"


async def test_get_document_not_found(async_session: AsyncSession):
    found = await get_document(async_session, 9999)
    assert found is None


async def test_delete_document(async_session: AsyncSession):
    doc = await create_document(async_session, "To Delete", "Content", None, "FAQ")
    await async_session.commit()

    result = await delete_document(async_session, doc.id)
    assert result is True

    remaining = await async_session.get(Document, doc.id)
    assert remaining is None


async def test_delete_document_not_found(async_session: AsyncSession):
    result = await delete_document(async_session, 9999)
    assert result is False


async def test_create_document_without_source_url(async_session: AsyncSession):
    doc = await create_document(
        session=async_session,
        title="No URL Doc",
        content="Content here",
        source_url=None,
        category="Guide",
    )
    await async_session.commit()

    assert doc.source_url is None
    assert doc.category == "Guide"

    retrieved = await get_document(async_session, doc.id)
    assert retrieved.source_url is None
