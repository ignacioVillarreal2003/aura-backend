"""Tests for the shared StructuredProcessingService base and its subclasses:
orchestration, JSON parsing, error mapping, JSON-repair loop and post-filtering.
Uses fakes so no real LLM is required."""

import json
import types

import pytest

from app.application.services.processing.document_classify_service.document_classify_service import (
    DocumentClassifyService,
)
from app.application.services.processing.document_classify_service.exceptions.document_classify_service_exceptions import (
    DocumentClassifyServiceException,
)
from app.application.services.processing.fragment_contextualize_service.fragment_contextualize_service import (
    FragmentContextualizeService,
)
from app.application.services.processing.graph_query_translation_service.exceptions.graph_query_translation_service_exceptions import (
    GraphQueryTranslationServiceException,
)
from app.application.services.processing.graph_query_translation_service.graph_query_translation_service import (
    GraphQueryTranslationService,
)
from app.application.services.processing.graph_query_translation_service.graph_query_translation_settings import (
    GraphQueryTranslationServiceSettings,
)
from app.domain.constants.document_type import DocumentType
from app.domain.constants.graph.query_intent import QueryIntent
from app.domain.dtos.processing.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.processing.document_classify.classify_document_response import ClassifyDocumentResponse
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_request import (
    GraphOntology,
    TranslateGraphQueryRequest,
)
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_response import (
    TranslateGraphQueryResponse,
)
from app.infrastructure.llm.ollama_llm.exceptions.ollama_llm_invoker_exceptions import LLMInvocationError


class _LLM:
    def bind(self, **_k):
        return self


class _Facade:
    async def get_llm_json(self):
        return _LLM()


class _Invoker:
    """Returns successive responses from a list; repeats the last one."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def call_llm_content(self, llm, llm_input):
        self.calls += 1
        return self._responses[min(self.calls - 1, len(self._responses) - 1)]


class _BoomInvoker:
    async def call_llm_content(self, llm, llm_input):
        raise LLMInvocationError("down")


_USER = types.SimpleNamespace(id=1)


def _classify_request():
    return ClassifyDocumentRequest(document_name="Doc.pdf", content="Contenido del documento.")


_VALID_CLASSIFY_JSON = json.dumps({
    "type": list(DocumentType)[0].value,
    "category": "normativa",
    "description": "Un documento de prueba.",
})

_VALID_TRANSLATE_JSON = json.dumps({
    "intent": QueryIntent.FIND_ENTITY.value,
    "parameters": {},
    "confidence": 0.9,
    "reasoning": None,
})


def _translate_request():
    return TranslateGraphQueryRequest(
        question="¿Quién firmó la resolución?",
        ontology=GraphOntology(entity_types=["person"], relation_types=["signed"]),
    )


class TestHappyPath:
    async def test_classify_returns_parsed_response(self):
        invoker = _Invoker([_VALID_CLASSIFY_JSON])
        svc = DocumentClassifyService(_Facade(), invoker)
        result = await svc.classify_document(_classify_request(), _USER)
        assert isinstance(result, ClassifyDocumentResponse)
        assert result.category == "normativa"
        assert invoker.calls == 1

    async def test_json_wrapped_in_markdown_is_parsed(self):
        wrapped = f"```json\n{_VALID_CLASSIFY_JSON}\n```"
        svc = DocumentClassifyService(_Facade(), _Invoker([wrapped]))
        result = await svc.classify_document(_classify_request(), _USER)
        assert isinstance(result, ClassifyDocumentResponse)


class TestErrorMapping:
    async def test_unparseable_json_raises_502(self):
        svc = DocumentClassifyService(_Facade(), _Invoker(["esto no es json"]))
        with pytest.raises(DocumentClassifyServiceException) as ei:
            await svc.classify_document(_classify_request(), _USER)
        assert ei.value.status_code == 502

    async def test_schema_violation_raises_502(self):
        bad = json.dumps({"type": "not-a-type", "category": "", "description": "x"})
        svc = DocumentClassifyService(_Facade(), _Invoker([bad]))
        with pytest.raises(DocumentClassifyServiceException) as ei:
            await svc.classify_document(_classify_request(), _USER)
        assert ei.value.status_code == 502

    async def test_llm_failure_raises_502(self):
        svc = DocumentClassifyService(_Facade(), _BoomInvoker())
        with pytest.raises(DocumentClassifyServiceException) as ei:
            await svc.classify_document(_classify_request(), _USER)
        assert ei.value.status_code == 502


class TestTruncation:
    def test_truncate_helper(self):
        svc = FragmentContextualizeService(_Facade(), _Invoker(["{}"]))
        assert svc._truncate("x" * 100, 10, 1, "content") == "x" * 10
        assert svc._truncate("short", 10, 1, "content") == "short"


class TestRepairLoop:
    async def test_classify_has_no_repair_single_call(self):
        invoker = _Invoker(["bad", "alsobad"])
        svc = DocumentClassifyService(_Facade(), invoker)
        with pytest.raises(DocumentClassifyServiceException):
            await svc.classify_document(_classify_request(), _USER)
        assert invoker.calls == 1

    async def test_translation_repairs_then_succeeds(self):
        invoker = _Invoker(["no json todavía", _VALID_TRANSLATE_JSON])
        svc = GraphQueryTranslationService(_Facade(), invoker)
        result = await svc.translate_graph_query(_translate_request(), _USER)
        assert isinstance(result, TranslateGraphQueryResponse)
        assert result.intent == QueryIntent.FIND_ENTITY
        assert invoker.calls == 2

    async def test_translation_exhausts_repair_then_raises(self):
        invoker = _Invoker(["bad", "still bad", "and bad"])
        settings = GraphQueryTranslationServiceSettings(_env_file=None, max_repair_attempts=1)
        svc = GraphQueryTranslationService(_Facade(), invoker, settings)
        with pytest.raises(GraphQueryTranslationServiceException):
            await svc.translate_graph_query(_translate_request(), _USER)
        assert invoker.calls == 2
