"""Tests for the document summary and action services after migration to the
shared structured (JSON) base: default flags, synthetic instruction messages,
JSON parsing into title/description/body, action guidance, Markdown fallback,
and reduction-prompt wiring."""

import types

import pytest

from app.application.services.user_interactions.document_action_service.document_action_service import (
    DocumentActionService,
)
from app.application.services.user_interactions.document_summary_service.document_summary_service import (
    DocumentSummaryService,
)
from app.domain.constants.document_action_type import DocumentActionType
from app.domain.dtos.user_interactions.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.user_interactions.document_action.document_action_stream_events import (
    DocumentActionStreamComplete,
)
from app.domain.dtos.user_interactions.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.user_interactions.document_summary.document_summary_stream_events import (
    DocumentSummaryStreamComplete,
)

_SUMMARY_JSON = (
    '{"title": "Informe técnico", '
    '"description": "Síntesis introductoria del documento.", '
    '"summary": "## Sección\\nContenido **clave** del resumen."}'
)
_ACTION_JSON = (
    '{"title": "Fechas del documento", '
    '"description": "Listado de fechas relevantes.", '
    '"result": "## Resultado\\n- 01/01/2024\\n- 15/06/2024"}'
)


class _LLM:
    def bind(self, **_k):
        return self


class _Facade:
    async def get_llm_base(self):
        return _LLM()

    async def get_llm_json(self):
        return _LLM()


class _Invoker:
    def __init__(self, content):
        self._content = content

    async def call_llm_content(self, llm, llm_input):
        return self._content


def _frag(i, n=80):
    from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
    return FragmentResponse(id=i, content="x" * n, fragment_index=i, document={"id": 1, "name": "D"})


class _Provider:
    def __init__(self, doc_frags):
        self._doc = doc_frags

    async def retrieve_context_fragments_by_question_request(self, authenticated_user, request):
        return types.SimpleNamespace(fragments=[])

    async def retrieve_context_fragments_by_document(self, authenticated_user, document_ids):
        return types.SimpleNamespace(fragments=self._doc)


_USER = types.SimpleNamespace(id=1)


def _summary_svc(content=_SUMMARY_JSON, frags=None):
    return DocumentSummaryService(_Facade(), _Invoker(content), _Provider(frags or [_frag(1)]))


def _action_svc(content=_ACTION_JSON, frags=None):
    return DocumentActionService(_Facade(), _Invoker(content), _Provider(frags or [_frag(1)]))


class TestDefaults:
    @pytest.mark.parametrize("cls", [DocumentSummaryService, DocumentActionService])
    def test_process_documents_by_default(self, cls):
        assert cls.default_process_documents is True
        assert cls.default_retrieve_context is False

    @pytest.mark.parametrize("cls", [DocumentSummaryService, DocumentActionService])
    def test_json_mode_enabled(self, cls):
        assert cls.uses_json_mode is True

    @pytest.mark.parametrize("cls", [DocumentSummaryService, DocumentActionService])
    def test_four_reduction_prompts_with_placeholders(self, cls):
        for attr in ("map_human_prompt", "reduce_human_prompt"):
            v = getattr(cls, attr)
            assert "{fragments}" in v and "{input}" not in v
        assert "{context}" in cls.human_prompt


class TestSummary:
    def test_synthetic_instruction_message(self):
        svc = _summary_svc()
        req = DocumentSummaryRequest(document_ids=[1, 2], chat_id=1)
        state = svc._build_state(req, _USER)
        assert state.current_message.content
        assert state.process_documents is True and state.retrieve_context is False

    async def test_execute_parses_json_into_title_description_summary(self):
        svc = _summary_svc(frags=[_frag(1), _frag(2)])
        res = await svc.execute_document_summary(DocumentSummaryRequest(document_ids=[1, 2], chat_id=1), _USER)
        assert res.title == "Informe técnico"
        assert res.description == "Síntesis introductoria del documento."
        assert res.summary == "## Sección\nContenido **clave** del resumen."
        assert len(res.fragments) == 2

    async def test_markdown_fallback_when_not_json(self):
        svc = _summary_svc(content="# Título suelto\n\nIntro.\n\n## Cuerpo\ndetalle")
        res = await svc.execute_document_summary(DocumentSummaryRequest(document_ids=[1], chat_id=1), _USER)
        assert res.title == "Título suelto"
        assert res.description == "Intro."
        assert "## Cuerpo" in res.summary

    async def test_stream_emits_complete(self):
        svc = _summary_svc()
        events = [
            e async for e in svc.execute_document_summary_stream(
                DocumentSummaryRequest(document_ids=[1], chat_id=1), _USER
            )
        ]
        completes = [e for e in events if isinstance(e, DocumentSummaryStreamComplete)]
        assert len(completes) == 1
        assert completes[0].result.summary == "## Sección\nContenido **clave** del resumen."


class TestAction:
    def test_instruction_becomes_current_message(self):
        svc = _action_svc()
        req = DocumentActionRequest(document_ids=[1], instruction="Analiza esto", chat_id=1)
        state = svc._build_state(req, _USER)
        assert state.current_message.content == "Analiza esto"

    def test_system_prompt_includes_action_guidance(self):
        svc = _action_svc()
        req = DocumentActionRequest(
            document_ids=[1], instruction="x", action=DocumentActionType.compare, chat_id=1
        )
        prompt = svc._system_prompt(req)
        assert "comparación detallada" in prompt
        assert "convergencias y divergencias" in prompt

    def test_system_prompt_default_guidance_without_action(self):
        svc = _action_svc()
        req = DocumentActionRequest(document_ids=[1], instruction="x", chat_id=1)
        prompt = svc._system_prompt(req)
        assert "Ejecutar la instrucción del usuario de forma precisa" in prompt
        assert "única fuente" in prompt

    async def test_execute_parses_json_and_echoes_request_fields(self):
        svc = _action_svc(frags=[_frag(1)])
        req = DocumentActionRequest(
            document_ids=[1], instruction="Resume", action=DocumentActionType.summarize, chat_id=1
        )
        res = await svc.execute_document_action(req, _USER)
        assert res.title == "Fechas del documento"
        assert res.description == "Listado de fechas relevantes."
        assert res.result == "## Resultado\n- 01/01/2024\n- 15/06/2024"
        assert res.action == DocumentActionType.summarize
        assert res.instruction == "Resume"

    async def test_stream_emits_complete(self):
        svc = _action_svc()
        events = [
            e async for e in svc.execute_document_action_stream(
                DocumentActionRequest(document_ids=[1], instruction="x", chat_id=1), _USER
            )
        ]
        completes = [e for e in events if isinstance(e, DocumentActionStreamComplete)]
        assert len(completes) == 1
        assert completes[0].result.result.startswith("## Resultado")
