from app.application.services.generation_shared.processors.history_summarization_processor.history_summarization_processor import (
    HistorySummarizationProcessor,
)
from app.application.services.generation_shared.processors.history_summarization_processor.history_summarization_settings import (
    HistorySummarizationSettings,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


class _Facade:
    async def get_llm_base(self):
        return _Llm()


class _Llm:
    def bind(self, **_):
        return self


class _Invoker:
    def __init__(self, content="resumen generado", boom=False):
        self.content = content
        self.boom = boom
        self.calls = 0

    async def call_llm_content(self, llm, llm_input):
        self.calls += 1
        if self.boom:
            raise RuntimeError("llm down")
        return self.content


def _state(turns: int, size: int) -> GenerationState:
    msgs = [
        Message(
            role=MessageRole.human if i % 2 == 0 else MessageRole.assistant,
            content="x" * size,
        )
        for i in range(turns)
    ]
    msgs.append(Message(role=MessageRole.human, content="pregunta actual"))
    return GenerationState.create(messages=msgs, chat_id=1, authenticated_user=None)


_SETTINGS = HistorySummarizationSettings(summarize_over_chars=2_000, max_summary_chars=500)


def _proc(invoker):
    return HistorySummarizationProcessor(_Facade(), invoker, _SETTINGS)


class TestIsNeeded:
    def test_not_needed_when_history_small(self):
        proc = _proc(_Invoker())
        assert proc.is_needed(_state(turns=2, size=100), history_window=4) is False

    def test_not_needed_with_single_turn(self):
        proc = _proc(_Invoker())
        assert proc.is_needed(_state(turns=1, size=10_000), history_window=4) is False

    def test_needed_when_window_exceeds_threshold(self):
        proc = _proc(_Invoker())
        assert proc.is_needed(_state(turns=4, size=1_000), history_window=4) is True


class TestRun:
    async def test_sets_summary_capped(self):
        invoker = _Invoker(content="r" * 1_000)
        proc = _proc(invoker)
        state = _state(turns=4, size=1_000)
        await proc.run(state, history_window=4)
        assert invoker.calls == 1
        assert state.history_summary is not None and len(state.history_summary) == 500

    async def test_skips_when_not_needed(self):
        invoker = _Invoker()
        proc = _proc(invoker)
        state = _state(turns=2, size=100)
        await proc.run(state, history_window=4)
        assert invoker.calls == 0
        assert state.history_summary is None

    async def test_degrades_gracefully_on_llm_failure(self):
        invoker = _Invoker(boom=True)
        proc = _proc(invoker)
        state = _state(turns=4, size=1_000)
        await proc.run(state, history_window=4)
        assert state.history_summary is None
