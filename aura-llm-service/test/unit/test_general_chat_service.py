import types

from app.application.services.user_interactions.general_chat_service.general_chat_service import GeneralChatService
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.general_chat.general_chat_request import GeneralChatRequest
from app.domain.dtos.user_interactions.general_chat.general_chat_stream_events import (
    GeneralChatStreamComplete,
    GeneralChatStreamDelta,
    GeneralChatStreamProgress,
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
    """Returns reformulation JSON for the reformulation step, plain text otherwise."""

    async def call_llm_content(self, llm, llm_input):
        system = llm_input[0].content
        if "reescritura" in system or "preparación de consultas" in system:
            return '{"base_question": "q reescrita", "keywords": ["k1"]}'
        return "Respuesta directa de AURA."


class _Stream:
    def __init__(self, chunks):
        self._chunks = chunks

    async def stream_llm_content(self, llm, llm_input):
        for c in self._chunks:
            yield c


def _frag(i):
    from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
    return FragmentResponse(id=i, content="contexto", fragment_index=i, document={"id": 1, "name": "D"})


class _Provider:
    def __init__(self):
        self.retrieval_calls = 0

    async def retrieve_context_fragments_by_question_request(self, authenticated_user, request):
        self.retrieval_calls += 1
        return types.SimpleNamespace(fragments=[_frag(1)])

    async def retrieve_context_fragments_by_document(self, authenticated_user, document_ids):
        return types.SimpleNamespace(fragments=[_frag(2)])


_USER = types.SimpleNamespace(id=1)
_MSGS = [Message(role=MessageRole.human, content="Hola, ¿qué podés hacer?")]


def _svc(chunks=("Hola", " mundo"), provider=None):
    return GeneralChatService(_Facade(), _Invoker(), _Stream(chunks), provider or _Provider())


class TestDefaults:
    def test_both_flags_off_by_default(self):
        svc = _svc()
        state = svc._build_state(GeneralChatRequest(messages=_MSGS, chat_id=1), _USER)
        assert state.retrieve_context is False and state.process_documents is False

    def test_reduction_prompts_present(self):
        for attr in ("map_human_prompt", "reduce_human_prompt"):
            v = getattr(GeneralChatService, attr)
            assert "{query}" in v and "{fragments}" in v and "{input}" not in v
        assert "{context}" in GeneralChatService.human_prompt and "{input}" in GeneralChatService.human_prompt


class TestPlainChat:
    async def test_sync_no_retrieval_by_default(self):
        provider = _Provider()
        svc = _svc(provider=provider)
        res = await svc.execute_general_chat(
            GeneralChatRequest(messages=_MSGS, chat_id=1), _USER
        )
        assert res.answer == "Respuesta directa de AURA."
        assert provider.retrieval_calls == 0 and res.fragments == []
        assert res.messages[-1].role == MessageRole.assistant

    async def test_stream_plain_chat_no_progress_search(self):
        svc = _svc(chunks=("Resp", "uesta"))
        events = [
            e async for e in svc.execute_general_chat_stream(
                GeneralChatRequest(messages=_MSGS, chat_id=1), _USER
            )
        ]
        steps = [e.step for e in events if isinstance(e, GeneralChatStreamProgress)]
        assert "searching" not in steps and "reformulating" not in steps
        assert [e.text for e in events if isinstance(e, GeneralChatStreamDelta)] == ["Resp", "uesta"]
        assert any(isinstance(e, GeneralChatStreamComplete) for e in events)


class TestRagOptIn:
    async def test_retrieve_context_flag_enables_corpus(self):
        provider = _Provider()
        svc = _svc(provider=provider)
        events = [
            e async for e in svc.execute_general_chat_stream(
                GeneralChatRequest(
                    messages=_MSGS, chat_id=1, retrieve_context=True
                ),
                _USER,
            )
        ]
        steps = [e.step for e in events if isinstance(e, GeneralChatStreamProgress)]
        assert "reformulating" in steps and "searching" in steps
        assert provider.retrieval_calls >= 1
        complete = next(e for e in events if isinstance(e, GeneralChatStreamComplete))
        assert complete.result.fragments
