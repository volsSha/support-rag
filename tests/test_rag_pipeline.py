from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.safety import RAGResult, Source, ThinkEvent, compute_confidence
from src.rag.pipeline import RAGPipeline


class TestSource:
    def test_valid_source(self):
        s = Source(title="Doc Title", url="https://example.com", chunk_id=1)
        assert s.title == "Doc Title"
        assert s.url == "https://example.com"
        assert s.chunk_id == 1

    def test_source_without_url(self):
        s = Source(title="Doc", url=None, chunk_id=2)
        assert s.url is None


class TestRAGResult:
    def test_creation(self):
        sources = [Source(title="A", url="https://a.com", chunk_id=1)]
        r = RAGResult(answer="test", sources=sources, confidence=0.85, escalated=False)
        assert r.answer == "test"
        assert len(r.sources) == 1
        assert r.confidence == 0.85
        assert r.escalated is False

    def test_serialization(self):
        sources = [Source(title="A", url=None, chunk_id=1)]
        r = RAGResult(answer="ans", sources=sources, confidence=1.0, escalated=True)
        d = r.model_dump()
        assert d["escalated"] is True
        assert d["sources"][0]["chunk_id"] == 1


class TestComputeConfidence:
    def test_high_reranker_low_distance(self):
        confidence, escalated = compute_confidence(
            top_score=0.95, top_distance=0.2, threshold=0.7,
        )
        assert confidence > 0.7
        assert escalated is False

    def test_low_reranker_high_distance_escalated(self):
        confidence, escalated = compute_confidence(
            top_score=0.1, top_distance=1.5, threshold=0.7,
        )
        assert escalated is True

    def test_zero_distance(self):
        confidence, escalated = compute_confidence(
            top_score=1.0, top_distance=0.0, threshold=0.7,
        )
        assert confidence > 0.9
        assert escalated is False

    def test_max_distance(self):
        confidence, escalated = compute_confidence(
            top_score=0.0, top_distance=2.0, threshold=0.7,
        )
        assert confidence == 0.0
        assert escalated is True

    def test_distance_clamped_to_one(self):
        confidence, escalated = compute_confidence(
            top_score=0.5, top_distance=3.0, threshold=0.7,
        )
        distance_part = max(0.0, 1.0 - (3.0 / 2.0))
        expected = 0.6 * distance_part + 0.4 * 0.5
        assert confidence == expected
        assert escalated is True

    def test_threshold_boundary(self):
        _, escalated_at = compute_confidence(0.5, 0.7, threshold=0.7)
        _, escalated_above = compute_confidence(0.5, 0.71, threshold=0.7)
        assert escalated_at is False
        assert escalated_above is True


class TestRAGPipeline:
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.reranker.top_k = 20
        settings.reranker.top_n = 5
        settings.retrieval.similarity_threshold = 0.7
        settings.retrieval.context_max_tokens = 3000
        return settings

    @pytest.fixture
    def pipeline(self, mock_settings):
        return RAGPipeline(db_connection=MagicMock(), settings=mock_settings)

    @pytest.mark.asyncio
    async def test_process_query_no_results(self, pipeline):
        with (
            patch("src.rag.embeddings.encode_query", return_value=[0.1] * 384),
            patch("src.db.vec.search_similar", return_value=[]),
        ):
            results = []
            async for item in pipeline.process_query("test query", user_id=1):
                results.append(item)

        rag_results = [r for r in results if isinstance(r, RAGResult)]
        think_events = [r for r in results if isinstance(r, ThinkEvent)]
        assert len(rag_results) == 1
        assert rag_results[0].escalated is True
        assert rag_results[0].confidence == 0.0
        assert len(think_events) >= 1

    @pytest.mark.asyncio
    async def test_process_query_escalated(self, pipeline):
        mock_chunk = MagicMock()
        mock_chunk.id = 1
        mock_chunk.content = "Some content"
        mock_chunk.document_id = 10
        mock_doc = MagicMock()
        mock_doc.title = "Test Doc"
        mock_doc.source_url = "https://example.com"

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        exec_result = MagicMock()
        exec_result.all.return_value = [(mock_chunk, mock_doc)]
        mock_session.execute = AsyncMock(return_value=exec_result)

        with (
            patch("src.rag.embeddings.encode_query", return_value=[0.1] * 384),
            patch("src.db.vec.search_similar", return_value=[(1, 1.5)]),
            patch("src.rag.reranker.rerank", return_value=[]),
            patch("src.db.engine.async_session_factory") as mock_session_factory,
        ):
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            results = []
            async for item in pipeline.process_query("test", user_id=1):
                results.append(item)

        rag_results = [r for r in results if isinstance(r, RAGResult)]
        think_events = [r for r in results if isinstance(r, ThinkEvent)]
        assert len(rag_results) == 1
        assert rag_results[0].escalated is True
        assert len(think_events) >= 1

    @pytest.mark.asyncio
    async def test_process_query_successful(self, pipeline):
        reranked = [
            {
                "chunk_id": 1,
                "content": "Answer content here",
                "title": "Knowledge Base",
                "url": "https://docs.example.com",
                "rerank_score": 0.9,
                "distance": 0.3,
            },
        ]

        async def mock_stream(messages):
            yield "Hello"
            yield " world"

        mock_llm = MagicMock()
        mock_llm.stream_completion = mock_stream

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.id = 1
        mock_chunk.content = "Answer content here"
        mock_chunk.document_id = 10
        mock_doc = MagicMock()
        mock_doc.title = "Knowledge Base"
        mock_doc.source_url = "https://docs.example.com"
        exec_result = MagicMock()
        exec_result.all.return_value = [(mock_chunk, mock_doc)]
        mock_session.execute = AsyncMock(return_value=exec_result)

        with (
            patch("src.rag.embeddings.encode_query", return_value=[0.1] * 384),
            patch("src.db.vec.search_similar", return_value=[(1, 0.3)]),
            patch("src.rag.reranker.rerank", return_value=reranked),
            patch("src.rag.context.build_context", return_value="context"),
            patch("src.llm.openrouter.get_llm_client", return_value=mock_llm),
            patch("src.db.engine.async_session_factory") as mock_session_factory,
        ):
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            results = []
            async for item in pipeline.process_query("test", user_id=1):
                results.append(item)

        token_results = [r for r in results if isinstance(r, str)]
        rag_results = [r for r in results if isinstance(r, RAGResult)]
        think_events = [r for r in results if isinstance(r, ThinkEvent)]

        assert token_results == ["Hello", " world"]
        assert len(rag_results) == 1
        assert rag_results[0].answer == "Hello world"
        assert rag_results[0].escalated is False
        assert len(rag_results[0].sources) == 1
        assert len(think_events) >= 1

    @staticmethod
    def _async_iter(items):
        async def gen():
            for item in items:
                yield item
        return gen()

    @pytest.mark.asyncio
    async def test_ingest_document(self, pipeline):
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.content = "Long document content..."

        mock_session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = mock_doc
        mock_session.execute = AsyncMock(return_value=exec_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        with (
            patch("src.rag.chunker.chunk_document", MagicMock(return_value=[MagicMock(content="Long document content...")])),
            patch("src.rag.embeddings.encode_documents", return_value=[[0.1] * 384]),
            patch("src.db.vec.insert_embedding"),
            patch("src.db.engine.async_session_factory") as mock_session_factory,
        ):
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await pipeline.ingest_document(1)

        assert count == 1

    @pytest.mark.asyncio
    async def test_ingest_document_not_found(self, pipeline):
        mock_session = AsyncMock()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=exec_result)

        with (
            patch("src.db.engine.async_session_factory") as mock_session_factory,
        ):
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await pipeline.ingest_document(999)
        assert count == 0

    @pytest.mark.asyncio
    async def test_delete_document_vectors(self, pipeline):
        with patch("src.db.vec.delete_embeddings") as mock_delete:
            await pipeline.delete_document_vectors([1, 2, 3])
            mock_delete.assert_called_once_with(pipeline._db, [1, 2, 3])

    @pytest.mark.asyncio
    async def test_get_pipeline_singleton(self):
        import src.rag.pipeline as pipeline_mod
        original = pipeline_mod._pipeline
        pipeline_mod._pipeline = None

        with patch("src.rag.pipeline.get_settings"):
            p1 = pipeline_mod.get_pipeline()
            p2 = pipeline_mod.get_pipeline()
            assert p1 is p2

        pipeline_mod._pipeline = original
