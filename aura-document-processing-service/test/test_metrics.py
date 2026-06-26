from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from prometheus_client import REGISTRY

from app.application.services.document.document_ingestion_service.document_ingestion_service import (
    DocumentIngestionService,
    _ChunkingOutcome,
)
from app.application.services.document.document_ingestion_service.exceptions.document_ingestion_service_exception import (
    DocumentIngestionServiceReadException,
)
from app.configuration.metrics import llm_result_from_status, observe_stage
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.llm_provider.exceptions.llm_provider_exception import (
    LlmProviderException,
    LlmProviderInvalidResponseException,
)
from app.infrastructure.http.llm_provider.llm_provider import LlmProvider


def _counter(name: str, labels: dict) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def _histogram_count(name: str, labels: dict | None = None) -> float:
    return REGISTRY.get_sample_value(f"{name}_count", labels or {}) or 0.0


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(id=1, email="u@test.com", roles=[], permissions=[])



class TestLlmResultFromStatus:
    @pytest.mark.parametrize(
        "status,expected",
        [(504, "timeout"), (503, "unavailable"), (500, "http_error"), (None, "http_error")],
    )
    def test_mapping(self, status, expected):
        assert llm_result_from_status(status) == expected



class TestObserveStage:
    def test_records_duration_on_success(self):
        name = "aura_document_pipeline_stage_duration_seconds"
        before = _histogram_count(name, {"stage": "unit_stage"})
        with observe_stage("unit_stage"):
            pass
        assert _histogram_count(name, {"stage": "unit_stage"}) == before + 1

    def test_records_duration_and_propagates_on_exception(self):
        name = "aura_document_pipeline_stage_duration_seconds"
        before = _histogram_count(name, {"stage": "boom_stage"})
        with pytest.raises(ValueError):
            with observe_stage("boom_stage"):
                raise ValueError("x")
        assert _histogram_count(name, {"stage": "boom_stage"}) == before + 1



class TestLlmProviderMetrics:
    def _provider(self):
        return LlmProvider(http_client=AsyncMock(), llm_provider_settings=MagicMock())

    async def test_success_increments_success_counter(self):
        provider = self._provider()
        provider._do_post_llm_json = AsyncMock(return_value="ok")
        before = _counter("aura_llm_requests_total", {"operation": "classify_document", "result": "success"})

        result = await provider._post_llm_json(
            url="http://llm", json_body={}, timeout=1.0,
            response_model=MagicMock(), authenticated_user=_user(),
            operation="classify_document",
        )
        assert result == "ok"
        after = _counter("aura_llm_requests_total", {"operation": "classify_document", "result": "success"})
        assert after == before + 1

    async def test_timeout_status_maps_to_timeout_result(self):
        provider = self._provider()
        provider._do_post_llm_json = AsyncMock(
            side_effect=LlmProviderException("timeout", status_code=504)
        )
        before = _counter("aura_llm_requests_total", {"operation": "enrich_fragment", "result": "timeout"})

        with pytest.raises(LlmProviderException):
            await provider._post_llm_json(
                url="http://llm", json_body={}, timeout=1.0,
                response_model=MagicMock(), authenticated_user=_user(),
                operation="enrich_fragment",
            )
        after = _counter("aura_llm_requests_total", {"operation": "enrich_fragment", "result": "timeout"})
        assert after == before + 1

    async def test_invalid_response_increments_invalid_response_result(self):
        provider = self._provider()
        provider._do_post_llm_json = AsyncMock(
            side_effect=LlmProviderInvalidResponseException("bad json")
        )
        before = _counter(
            "aura_llm_requests_total",
            {"operation": "translate_graph_query", "result": "invalid_response"},
        )

        with pytest.raises(LlmProviderInvalidResponseException):
            await provider._post_llm_json(
                url="http://llm", json_body={}, timeout=1.0,
                response_model=MagicMock(), authenticated_user=_user(),
                operation="translate_graph_query",
            )
        after = _counter(
            "aura_llm_requests_total",
            {"operation": "translate_graph_query", "result": "invalid_response"},
        )
        assert after == before + 1



class TestIngestionMetrics:
    def _service(self):
        return DocumentIngestionService(
            document_repository=AsyncMock(),
            fragment_repository=AsyncMock(),
            reader_factory=MagicMock(),
            text_cleaner_factory=MagicMock(),
            text_splitter_factory=MagicMock(),
            embedder_factory=MagicMock(),
            database_manager=AsyncMock(),
        )

    def _outcome(self):
        return _ChunkingOutcome(
            chunks=[MagicMock(embed_text=None, text="a")],
            splitter_type="classic",
            cleaner_type="basic",
            chunk_size=1,
            chunk_overlap=0,
        )

    async def test_success_increments_success_and_fragments(self):
        service = self._service()
        service._produce_chunks = AsyncMock(return_value=self._outcome())
        service._embed_chunks = AsyncMock(return_value=[[0.1]])
        service._build_fragments = MagicMock(return_value=[MagicMock(), MagicMock()])
        service._persist_fragments_and_update_document = AsyncMock()
        service._cleanup_temp_file = AsyncMock()

        before = _counter("aura_document_ingestion_total", {"result": "success"})
        frag_before = _histogram_count("aura_document_fragments_per_document")

        await service.process_document(
            document=MagicMock(id=1),
            local_file_path=Path("f.pdf"),
            user=_user(),
            enrich=False,
            graph_extract=False,
        )

        assert _counter("aura_document_ingestion_total", {"result": "success"}) == before + 1
        assert _histogram_count("aura_document_fragments_per_document") == frag_before + 1

    async def test_read_failure_attributes_stage_and_failure_counter(self):
        service = self._service()
        service._produce_chunks = AsyncMock(
            side_effect=DocumentIngestionServiceReadException("unreadable")
        )
        service._mark_document_as_failed = AsyncMock()
        service._cleanup_temp_file = AsyncMock()

        fail_before = _counter("aura_document_ingestion_total", {"result": "failure"})
        stage_before = _counter("aura_document_pipeline_stage_failures_total", {"stage": "read"})

        with pytest.raises(DocumentIngestionServiceReadException):
            await service.process_document(
                document=MagicMock(id=1),
                local_file_path=Path("f.pdf"),
                user=_user(),
                enrich=False,
                graph_extract=False,
            )

        assert _counter("aura_document_ingestion_total", {"result": "failure"}) == fail_before + 1
        assert _counter("aura_document_pipeline_stage_failures_total", {"stage": "read"}) == stage_before + 1
        service._mark_document_as_failed.assert_awaited_once()
