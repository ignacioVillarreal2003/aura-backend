import types
from dataclasses import dataclass

from app.application.exceptions.app_exception import AppException
from app.application.services.generation_shared.streaming_generation_service import StreamingGenerationService
from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


class _TestError(AppException):
    pass


@dataclass
class _Progress:
    step: str
    message: str


@dataclass
class _Complete:
    result: object


@dataclass
class _Error:
    message: str
    code: str


@dataclass
class _Delta:
    text: str


class _FakeLLM:
    def bind(self, **_kwargs):
        return self


class _Facade:
    async def get_llm_base(self):
        return _FakeLLM()

    async def get_llm_json(self):
        return _FakeLLM()


class _Invoker:
    def __init__(self, content="resultado"):
        self._content = content

    async def call_llm_content(self, llm, llm_input):
        return self._content


class _StreamInvoker:
    def __init__(self, chunks):
        self._chunks = chunks

    async def stream_llm_content(self, llm, llm_input):
        for chunk in self._chunks:
            yield chunk


class _Spy:
    def __init__(self):
        self.called = False

    async def run(self, *args, **kwargs):
        self.called = True


class _CommonClassVars:
    label = "test"
    exception_cls = _TestError
    unexpected_error_message = "ups"
    generation_step_message = "generando"
    human_prompt = "CTX:{context}\nIN:{input}"
    map_system_prompt = "es"
    map_human_prompt = "{query}|{fragments}"
    stream_progress_event = _Progress
    stream_complete_event = _Complete
    stream_error_event = _Error


class _Struct(_CommonClassVars, StructuredGenerationService):
    uses_json_mode = False

    def _system_prompt(self, request):
        return "sys"

    def _parse_output(self, raw, request):
        return {"parsed": raw}

    def _build_response(self, state, request, parsed, raw):
        return parsed


class _Stream(_CommonClassVars, StreamingGenerationService):
    stream_delta_event = _Delta

    def _system_prompt(self, request):
        return "sys"

    def _build_response(self, state, request, answer):
        return {"answer": answer}


def _request(**overrides):
    base = dict(
        messages=[Message(role=MessageRole.human, content="hola")],
        chat_id=1,
        document_ids=[],
        system_prompt=None,
        response_style=None,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _struct() -> _Struct:
    return _Struct(_Facade(), _Invoker(), document_context_provider=None)


def _spy(svc):
    spies = {n: _Spy() for n in ("reformulation", "context", "attached", "reduction")}
    svc._reformulation_processor = spies["reformulation"]
    svc._context_processor = spies["context"]
    svc._attached_processor = spies["attached"]
    svc._reduction_processor = spies["reduction"]
    return spies


class TestFlagResolution:
    def test_explicit_flags_win(self):
        svc = _struct()
        state = svc._build_state(_request(retrieve_context=True, process_documents=False, document_ids=[1]), None)
        assert state.retrieve_context is True and state.process_documents is False

    def test_none_uses_service_default(self):
        svc = _struct()
        state = svc._build_state(_request(retrieve_context=None, process_documents=None), None)
        assert state.retrieve_context is False and state.process_documents is False

    def test_mode_no_longer_infers_retrieval(self):
        svc = _struct()
        state = svc._build_state(_request(mode="rag"), None)
        assert state.retrieve_context is False

    def test_document_ids_no_longer_infers_process(self):
        svc = _struct()
        state = svc._build_state(_request(document_ids=[1, 2]), None)
        assert state.process_documents is False

    def test_subclass_default_applies(self):
        class _RagStruct(_Struct):
            default_retrieve_context = True
            default_process_documents = True

        svc = _RagStruct(_Facade(), _Invoker(), document_context_provider=None)
        state = svc._build_state(_request(), None)
        assert state.retrieve_context is True and state.process_documents is True


class TestCollectContextGating:
    async def test_retrieve_only(self):
        svc = _struct()
        spies = _spy(svc)
        state = svc._build_state(_request(retrieve_context=True, process_documents=False), None)
        await svc._collect_context(state)
        assert spies["reformulation"].called and spies["context"].called and spies["reduction"].called
        assert not spies["attached"].called

    async def test_process_documents_only(self):
        svc = _struct()
        spies = _spy(svc)
        state = svc._build_state(_request(retrieve_context=False, process_documents=True), None)
        await svc._collect_context(state)
        assert spies["attached"].called and spies["reduction"].called
        assert not spies["reformulation"].called and not spies["context"].called

    async def test_both(self):
        svc = _struct()
        spies = _spy(svc)
        state = svc._build_state(_request(retrieve_context=True, process_documents=True), None)
        await svc._collect_context(state)
        assert all(s.called for s in spies.values())

    async def test_neither_skips_everything(self):
        svc = _struct()
        spies = _spy(svc)
        state = svc._build_state(_request(retrieve_context=False, process_documents=False), None)
        await svc._collect_context(state)
        assert not any(s.called for s in spies.values())


class TestStructuredGenerate:
    async def test_generate_returns_parsed(self):
        svc = _struct()
        result = await svc.generate(_request(), authenticated_user=types.SimpleNamespace(id=1))
        assert result == {"parsed": "resultado"}

    async def test_generate_stream_emits_progress_then_complete(self):
        svc = _struct()
        events = [e async for e in svc.generate_stream(_request(), types.SimpleNamespace(id=1))]
        assert any(isinstance(e, _Progress) and e.step == "generation" for e in events)
        completes = [e for e in events if isinstance(e, _Complete)]
        assert len(completes) == 1 and completes[0].result == {"parsed": "resultado"}


class TestStreamingGenerate:
    def _svc(self, chunks):
        return _Stream(_Facade(), _Invoker(), _StreamInvoker(chunks), document_context_provider=None)

    async def test_stream_yields_deltas_then_complete(self):
        svc = self._svc(["Hola", " mundo"])
        events = [e async for e in svc.generate_stream(_request(), types.SimpleNamespace(id=1))]
        deltas = [e.text for e in events if isinstance(e, _Delta)]
        assert deltas == ["Hola", " mundo"]
        completes = [e for e in events if isinstance(e, _Complete)]
        assert len(completes) == 1 and completes[0].result == {"answer": "Hola mundo"}

    async def test_stream_empty_falls_back_to_non_stream(self):
        svc = self._svc([])
        events = [e async for e in svc.generate_stream(_request(), types.SimpleNamespace(id=1))]
        deltas = [e.text for e in events if isinstance(e, _Delta)]
        assert deltas == ["resultado"]
        assert any(isinstance(e, _Complete) for e in events)

    async def test_generate_sync_returns_answer(self):
        svc = self._svc(["x"])
        result = await svc.generate(_request(), types.SimpleNamespace(id=1))
        assert result == {"answer": "resultado"}
