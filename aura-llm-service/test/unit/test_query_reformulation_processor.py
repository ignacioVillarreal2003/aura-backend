from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_processor import (
    QueryReformulationProcessor,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_settings import (
    QueryReformulationSettings,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


class _FakeLLM:
    def bind(self, **_kwargs):
        return self


class _Facade:
    async def get_llm_json(self):
        return _FakeLLM()


class _Invoker:
    def __init__(self, content="", boom=False):
        self._content = content
        self._boom = boom

    async def call_llm_content(self, llm, llm_input):
        if self._boom:
            raise RuntimeError("llm down")
        return self._content


def _processor(invoker, **overrides) -> QueryReformulationProcessor:
    return QueryReformulationProcessor(_Facade(), invoker, QueryReformulationSettings(**overrides))


_HISTORY = [
    Message(role=MessageRole.human, content="¿Qué es el reglamento X?"),
    Message(role=MessageRole.assistant, content="Es una norma."),
]


class TestNormalizeKeywords:
    def test_from_list_dedup_preserving_order(self):
        p = _processor(_Invoker())
        assert p._normalize_keywords(["a", "B", "a", "b", "c"]) == "a B c"

    def test_from_string(self):
        p = _processor(_Invoker())
        assert p._normalize_keywords("uno  dos   tres") == "uno dos tres"

    def test_non_collection_returns_none(self):
        p = _processor(_Invoker())
        assert p._normalize_keywords(123) is None

    def test_budget_truncates(self):
        p = _processor(_Invoker(), max_keywords_tokens=256)
        terms = [f"kw{i}" for i in range(2000)]
        result = p._normalize_keywords(terms)
        assert result is not None and len(result) <= 1024


class TestTruncateField:
    def test_under_budget_unchanged(self):
        p = _processor(_Invoker())
        assert p._truncate_field("short", 500, "base") == "short"

    def test_over_budget_clipped(self):
        p = _processor(_Invoker())
        out = p._truncate_field("x" * 100, 10, "base")
        assert len(out) <= 40


class TestParse:
    def test_reads_base_only_when_should_rewrite(self):
        p = _processor(_Invoker())
        raw = '{"base_question": "reescrita", "keywords": ["a", "b"]}'
        with_rewrite = p._parse(raw, should_rewrite=True, use_keywords=True)
        assert with_rewrite.base_question == "reescrita" and with_rewrite.keyword_question == "a b"
        without_rewrite = p._parse(raw, should_rewrite=False, use_keywords=True)
        assert without_rewrite.base_question is None and without_rewrite.keyword_question == "a b"

    def test_keywords_gated(self):
        p = _processor(_Invoker())
        raw = '{"base_question": "r", "keywords": ["a"]}'
        result = p._parse(raw, should_rewrite=True, use_keywords=False)
        assert result.keyword_question is None


class TestReformulate:
    async def test_skips_call_when_nothing_to_do(self):
        invoker = _Invoker(boom=True)
        p = _processor(invoker, use_keywords=False)
        result = await p.reformulate(question="q", history_messages=[])
        assert result == result.__class__()

    async def test_success_returns_base_and_keywords(self):
        invoker = _Invoker(content='{"base_question": "X autocontenida", "keywords": ["k1", "k2"]}')
        p = _processor(invoker)
        result = await p.reformulate(question="X", history_messages=_HISTORY)
        assert result.base_question == "X autocontenida"
        assert result.keyword_question == "k1 k2"
        assert result.degraded is False

    async def test_llm_error_is_degraded(self):
        p = _processor(_Invoker(boom=True))
        result = await p.reformulate(question="X", history_messages=_HISTORY)
        assert result.degraded is True and result.base_question is None

    async def test_unparseable_output_is_degraded(self):
        p = _processor(_Invoker(content="no json aquí"))
        result = await p.reformulate(question="X", history_messages=_HISTORY)
        assert result.degraded is True


class TestRun:
    def _state(self) -> GenerationState:
        return GenerationState.create(
            messages=[*_HISTORY, Message(role=MessageRole.human, content="pregunta actual")],
            chat_id=1, retrieve_context=True, authenticated_user=None,
        )

    async def test_run_populates_state(self):
        invoker = _Invoker(content='{"base_question": "reescrita", "keywords": ["a", "b"]}')
        p = _processor(invoker)
        st = self._state()
        await p.run(st)
        assert st.base_question == "reescrita" and st.keyword_question == "a b"
        assert st.reformulation_degraded is False

    async def test_run_marks_degraded(self):
        p = _processor(_Invoker(boom=True))
        st = self._state()
        await p.run(st)
        assert st.reformulation_degraded is True
        assert st.base_question is None and st.keyword_question is None
