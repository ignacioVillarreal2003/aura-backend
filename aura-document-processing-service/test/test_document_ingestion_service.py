from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.processors.text_splitters.dtos.document_chunk import DocumentChunk
from app.application.services.document.document_ingestion_service.document_ingestion_service import (
    DocumentIngestionService,
)
from app.application.services.document.document_ingestion_service.document_ingestion_service_settings import (
    DocumentIngestionServiceSettings,
)
from app.application.services.document.document_ingestion_service.exceptions.document_ingestion_service_exception import (
    DocumentIngestionServiceCleanException,
    DocumentIngestionServiceEmbedException,
    DocumentIngestionServiceReadException,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser


def _user(user_id: int = 3) -> AuthenticatedUser:
    return AuthenticatedUser(id=user_id, email="u@test.com", roles=[], permissions=[])


def _document(doc_id: int = 1):
    return MagicMock(id=doc_id, created_by=3)


def _chunk(text: str, **kwargs) -> DocumentChunk:
    return DocumentChunk(text=text, **kwargs)


def _make_service(*, settings=None, embedder_factory=None, graph_pub=None, enrich_pub=None):
    return DocumentIngestionService(
        document_repository=AsyncMock(),
        fragment_repository=AsyncMock(),
        reader_factory=MagicMock(),
        text_cleaner_factory=MagicMock(),
        text_splitter_factory=MagicMock(),
        embedder_factory=embedder_factory or MagicMock(),
        database_manager=AsyncMock(),
        document_ingestion_service_settings=settings or DocumentIngestionServiceSettings(),
        graph_extraction_publisher=graph_pub,
        document_enrichment_publisher=enrich_pub,
    )



class TestReadDocument:
    async def test_no_capable_readers_raises(self):
        service = _make_service()
        service._reader_factory.get_capable_readers = MagicMock(return_value=[])
        with pytest.raises(DocumentIngestionServiceReadException):
            await service._read_document(_document(), Path("f.pdf"))

    async def test_falls_back_to_second_reader_when_first_fails(self):
        good = MagicMock()
        good.read = MagicMock(return_value="extracted text")
        bad = MagicMock()
        bad.read = MagicMock(side_effect=RuntimeError("corrupt"))
        service = _make_service()
        service._reader_factory.get_capable_readers = MagicMock(return_value=[bad, good])

        result = await service._read_document(_document(), Path("f.pdf"))
        assert result == "extracted text"

    async def test_all_readers_failing_raises(self):
        bad = MagicMock()
        bad.read = MagicMock(side_effect=RuntimeError("corrupt"))
        service = _make_service()
        service._reader_factory.get_capable_readers = MagicMock(return_value=[bad])
        with pytest.raises(DocumentIngestionServiceReadException):
            await service._read_document(_document(), Path("f.pdf"))

    async def test_empty_text_treated_as_failure(self):
        reader = MagicMock()
        reader.read = MagicMock(return_value="   ")
        service = _make_service()
        service._reader_factory.get_capable_readers = MagicMock(return_value=[reader])
        with pytest.raises(DocumentIngestionServiceReadException):
            await service._read_document(_document(), Path("f.pdf"))

    async def test_text_over_limit_rejected(self):
        reader = MagicMock()
        reader.read = MagicMock(return_value="x" * 100)
        settings = DocumentIngestionServiceSettings(max_raw_text_length=10)
        service = _make_service(settings=settings)
        service._reader_factory.get_capable_readers = MagicMock(return_value=[reader])
        with pytest.raises(DocumentIngestionServiceReadException):
            await service._read_document(_document(), Path("f.pdf"))



class TestCleanText:
    async def test_returns_cleaned_text(self):
        cleaner = MagicMock()
        cleaner.clean_text = MagicMock(return_value="clean")
        service = _make_service()
        service._cleaner_factory.cleaner = cleaner

        assert await service._clean_text(_document(), "  raw  ") == "clean"

    async def test_blank_output_raises_clean_exception(self):
        cleaner = MagicMock()
        cleaner.clean_text = MagicMock(return_value="   ")
        service = _make_service()
        service._cleaner_factory.cleaner = cleaner
        with pytest.raises(DocumentIngestionServiceCleanException):
            await service._clean_text(_document(), "raw")

    async def test_cleaner_error_is_wrapped(self):
        cleaner = MagicMock()
        cleaner.clean_text = MagicMock(side_effect=ValueError("boom"))
        service = _make_service()
        service._cleaner_factory.cleaner = cleaner
        with pytest.raises(DocumentIngestionServiceCleanException):
            await service._clean_text(_document(), "raw")



class TestEmbedChunks:
    async def test_returns_embeddings_on_success(self):
        embedder = AsyncMock()
        embedder.aembed_documents = AsyncMock(return_value=[[0.1], [0.2]])
        factory = MagicMock()
        factory.embedder = embedder
        service = _make_service(embedder_factory=factory)

        result = await service._embed_chunks(_document(), ["a", "b"])
        assert result == [[0.1], [0.2]]

    async def test_count_mismatch_raises(self):
        embedder = AsyncMock()
        embedder.aembed_documents = AsyncMock(return_value=[[0.1]])
        factory = MagicMock()
        factory.embedder = embedder
        service = _make_service(embedder_factory=factory)
        with pytest.raises(DocumentIngestionServiceEmbedException):
            await service._embed_chunks(_document(), ["a", "b"])

    async def test_embedder_error_is_wrapped(self):
        embedder = AsyncMock()
        embedder.aembed_documents = AsyncMock(side_effect=RuntimeError("gpu oom"))
        factory = MagicMock()
        factory.embedder = embedder
        service = _make_service(embedder_factory=factory)
        with pytest.raises(DocumentIngestionServiceEmbedException):
            await service._embed_chunks(_document(), ["a"])



class TestBuildFragments:
    def _embedder_factory(self):
        factory = MagicMock()
        factory.get_active_model_name = MagicMock(return_value="model-x")
        factory.get_vector_dimension = MagicMock(return_value=3)
        factory.get_active_embedding_identity = MagicMock(return_value="identity")
        return factory

    def test_builds_one_fragment_per_chunk_in_order(self):
        service = _make_service(embedder_factory=self._embedder_factory())
        chunks = [_chunk("first"), _chunk("second")]
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        fragments = service._build_fragments(_document(), chunks, embeddings)

        assert len(fragments) == 2
        assert [f.fragment_index for f in fragments] == [0, 1]
        assert [f.content for f in fragments] == ["first", "second"]
        assert fragments[0].embedding_model == "model-x"

    def test_mismatched_lengths_raise(self):
        service = _make_service(embedder_factory=self._embedder_factory())
        with pytest.raises(ValueError):
            service._build_fragments(_document(), [_chunk("only")], [[0.1], [0.2]])



class TestPublishEvents:
    async def test_enrichment_noop_when_publisher_absent(self):
        service = _make_service(enrich_pub=None)
        await service._publish_document_enrichment_event(_document(), _user())

    async def test_enrichment_published_when_present(self):
        pub = AsyncMock()
        service = _make_service(enrich_pub=pub)
        await service._publish_document_enrichment_event(_document(5), _user(3))
        pub.publish.assert_awaited_once_with(document_id=5, user=_user(3))

    async def test_enrichment_failure_is_swallowed(self):
        pub = AsyncMock()
        pub.publish = AsyncMock(side_effect=RuntimeError("broker down"))
        service = _make_service(enrich_pub=pub)
        await service._publish_document_enrichment_event(_document(), _user())

    async def test_graph_noop_when_publisher_absent(self):
        service = _make_service(graph_pub=None)
        await service._publish_graph_extraction_event(_document(), _user())

    async def test_graph_failure_is_swallowed(self):
        pub = AsyncMock()
        pub.publish = AsyncMock(side_effect=RuntimeError("broker down"))
        service = _make_service(graph_pub=pub)
        await service._publish_graph_extraction_event(_document(), _user())



class TestCleanupTempFile:
    async def test_missing_file_is_noop(self):
        path = MagicMock(spec=Path)
        path.exists = MagicMock(return_value=False)
        await DocumentIngestionService._cleanup_temp_file(path)
        path.unlink.assert_not_called()

    async def test_existing_file_is_unlinked(self):
        path = MagicMock(spec=Path)
        path.exists = MagicMock(return_value=True)
        await DocumentIngestionService._cleanup_temp_file(path)
        path.unlink.assert_called_once()

    async def test_unlink_error_is_swallowed(self):
        path = MagicMock(spec=Path)
        path.exists = MagicMock(return_value=True)
        path.unlink = MagicMock(side_effect=OSError("locked"))
        await DocumentIngestionService._cleanup_temp_file(path)
