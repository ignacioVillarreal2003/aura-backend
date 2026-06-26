import types

from app.application.services.user_interactions.document_question_service.document_question_service import (
    DocumentQuestionService,
)
from app.application.services.user_interactions.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.user_interactions.document_question.document_question_stream_events import (
    DocumentQuestionStreamComplete,
    DocumentQuestionStreamDelta,
    DocumentQuestionStreamMeta,
)


class _FakeLLM:
    def bind(self, **_kwargs):
        return self


class _Facade:
    async def get_llm_base(self):
        return _FakeLLM()

    async def get_llm_json(self):
        return _FakeLLM()


class _Invoker:
    async def call_llm_content(self, llm, llm_input):
        return "Respuesta basada en la documentación."


class _Stream:
    def __init__(self, chunks):
        self._chunks = chunks

    async def stream_llm_content(self, llm, llm_input):
        for c in self._chunks:
            yield c


def _frag(fragment_id: int, document_id: int = 1):
    from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
    return FragmentResponse(
        id=fragment_id, content=f"contenido {fragment_id}", fragment_index=fragment_id,
        document={"id": document_id, "name": f"Doc{document_id}"},
    )


class _Provider:
    def __init__(self, q_frags=None, doc_frags=None):
        self._q = q_frags if q_frags is not None else [_frag(1), _frag(2)]
        self._doc = doc_frags if doc_frags is not None else [_frag(9, document_id=9)]

    async def retrieve_context_fragments_by_question_request(self, authenticated_user, request):
        return types.SimpleNamespace(fragments=self._q)

    async def retrieve_context_fragments_by_document(self, authenticated_user, document_ids):
        return types.SimpleNamespace(fragments=self._doc)


def _svc(chunks=("Hola ", "mundo"), provider=None):
    return DocumentQuestionService(_Facade(), _Invoker(), _Stream(chunks), provider or _Provider())


_USER = types.SimpleNamespace(id=1)
_MSGS = [Message(role=MessageRole.human, content="¿Qué dice el documento?")]


class TestSettingsMapping:
    def test_profile_maps_to_shared_settings(self):
        s = DocumentQuestionServiceSettings()
        assert s.to_retrieval_settings().semantic_fragments_per_lane == 5
        assert s.to_retrieval_settings().max_fragments == 8
        assert s.to_reduction_settings().max_batch_chars == 6_000
        assert s.to_attached_settings().max_fragments == 10
        assert s.to_generation_settings().max_context_chars == 12_000


class TestDefaults:
    def test_retrieve_context_on_by_default(self):
        svc = _svc()
        state = svc._build_state(DocumentQuestionRequest(messages=_MSGS, chat_id=1), _USER)
        assert state.retrieve_context is True and state.process_documents is False

    def test_process_documents_opt_in(self):
        svc = _svc()
        req = DocumentQuestionRequest(messages=_MSGS, chat_id=1, document_ids=[9], process_documents=True)
        state = svc._build_state(req, _USER)
        assert state.process_documents is True


class TestSync:
    async def test_execute_returns_response_with_fragments(self):
        svc = _svc()
        res = await svc.execute_document_question(
            DocumentQuestionRequest(messages=_MSGS, chat_id=1), _USER
        )
        assert res.answer == "Respuesta basada en la documentación."
        assert res.question == "¿Qué dice el documento?"
        assert [f.id for f in res.fragments] == [1, 2]
        assert res.messages[-1].role == MessageRole.assistant


class TestStream:
    async def test_stream_emits_meta_deltas_and_complete(self):
        svc = _svc(chunks=("Resp", "uesta"))
        events = [
            e async for e in svc.execute_document_question_stream(
                DocumentQuestionRequest(messages=_MSGS, chat_id=1), _USER
            )
        ]
        assert any(isinstance(e, DocumentQuestionStreamMeta) for e in events)
        deltas = [e.text for e in events if isinstance(e, DocumentQuestionStreamDelta)]
        assert deltas == ["Resp", "uesta"]
        completes = [e for e in events if isinstance(e, DocumentQuestionStreamComplete)]
        assert len(completes) == 1 and completes[0].result.answer == "Respuesta"

    async def test_meta_includes_attached_when_process_documents(self):
        svc = _svc(provider=_Provider(q_frags=[_frag(1)], doc_frags=[_frag(9, document_id=9)]))
        req = DocumentQuestionRequest(messages=_MSGS, chat_id=1, document_ids=[9], process_documents=True)
        events = [e async for e in svc.execute_document_question_stream(req, _USER)]
        meta = next(e for e in events if isinstance(e, DocumentQuestionStreamMeta))
        doc_ids = {f.document_id for f in meta.fragments}
        assert 9 in doc_ids

    async def test_progress_steps_are_granular(self):
        svc = _svc()
        events = [
            e async for e in svc.execute_document_question_stream(
                DocumentQuestionRequest(messages=_MSGS, chat_id=1), _USER
            )
        ]
        steps = [e.step for e in events if hasattr(e, "step")]
        assert steps == ["processing", "reformulating", "searching", "generation"]

    async def test_reduction_runs_and_emits_progress_for_large_context(self):
        from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
        big = [
            FragmentResponse(
                id=i, content="contenido largo " * 1200, fragment_index=i,
                document={"id": 1, "name": "DocX"},
            )
            for i in range(1, 4)
        ]
        provider = _Provider(q_frags=big, doc_frags=[])
        reduce_calls = {"map": 0}

        class _MapInvoker:
            async def call_llm_content(self, llm, llm_input):
                if "aislar los pasajes relevantes" in llm_input[0].content:
                    reduce_calls["map"] += 1
                    return "pasaje relevante"
                return "Respuesta final."

        svc = DocumentQuestionService(_Facade(), _MapInvoker(), _Stream(("ok",)), provider)
        events = [
            e async for e in svc.execute_document_question_stream(
                DocumentQuestionRequest(messages=_MSGS, chat_id=1), _USER
            )
        ]
        steps = [e.step for e in events if hasattr(e, "step")]
        assert "reducing" in steps
        assert reduce_calls["map"] >= 1
