import types

from app.application.services.generation_shared.processors.context_retrieval_processor.context_retrieval_processor import (
    ContextRetrievalProcessor,
)
from app.application.services.generation_shared.processors.context_retrieval_processor.context_retrieval_settings import (
    ContextRetrievalSettings,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.exceptions.document_context_provider_exception import (
    DocumentContextProviderTimeoutException,
    DocumentContextProviderUnavailableException,
)


class _Provider:
    def __init__(self, fragments=None, error=None):
        self._fragments = fragments or []
        self._error = error

    async def retrieve_context_fragments_by_question_request(self, authenticated_user, request):
        if self._error is not None:
            raise self._error
        return types.SimpleNamespace(fragments=self._fragments)


def _processor(provider, **overrides) -> ContextRetrievalProcessor:
    return ContextRetrievalProcessor(provider, ContextRetrievalSettings(**overrides))


def _state(base=None, keywords=None) -> GenerationState:
    st = GenerationState.create(
        messages=[Message(role=MessageRole.human, content="pregunta original")],
        chat_id=1, retrieve_context=True, authenticated_user=types.SimpleNamespace(id=3),
    )
    st.base_question = base
    st.keyword_question = keywords
    return st


class TestRequestBuilding:
    def test_unique_query_texts_dedup_and_order(self):
        p = _processor(_Provider())
        assert p._unique_query_texts("a", "a", "b") == ["a", "b"]
        assert p._unique_query_texts("orig", "base", "kw") == ["orig", "base", "kw"]

    def test_lanes_mirror_for_original_base_keywords(self):
        p = _processor(_Provider())
        request = p._build_request(_state(base="reformulada", keywords="kw1 kw2"))
        expected = ["pregunta original", "reformulada", "kw1 kw2"]
        assert [q.text for q in request.semantic_queries] == expected
        assert [q.text for q in request.bm25_queries] == expected

    def test_only_original_lane_without_base_or_keywords(self):
        p = _processor(_Provider())
        request = p._build_request(_state())
        assert [q.text for q in request.semantic_queries] == ["pregunta original"]


class TestCharBudget:
    def test_disabled_by_default(self, make_fragment):
        p = _processor(_Provider())
        frs = [make_fragment(fragment_id=i + 1, content="y" * 400) for i in range(5)]
        assert p._apply_char_budget(frs) == frs

    def test_drops_whole_fragments_over_budget(self, make_fragment):
        p = _processor(_Provider(), max_context_chars=1_000)
        frs = [make_fragment(fragment_id=i + 1, content="y" * 400) for i in range(5)]
        assert len(p._apply_char_budget(frs)) == 2

    def test_keeps_at_least_one(self, make_fragment):
        p = _processor(_Provider(), max_context_chars=1_000)
        assert len(p._apply_char_budget([make_fragment(content="z" * 5_000)])) == 1


class TestRun:
    async def test_success(self, make_fragment):
        frs = [make_fragment(fragment_id=i + 1) for i in range(3)]
        p = _processor(_Provider(fragments=frs), max_fragments=50)
        st = _state()
        await p.run(st)
        assert len(st.fragments) == 3 and st.retrieval_degraded is False

    async def test_empty_is_not_degraded(self):
        p = _processor(_Provider(fragments=[]))
        st = _state()
        await p.run(st)
        assert st.fragments == [] and st.retrieval_degraded is False

    async def test_failure_marks_degraded(self):
        p = _processor(_Provider(error=DocumentContextProviderTimeoutException("t")))
        st = _state()
        await p.run(st)
        assert st.fragments == [] and st.retrieval_degraded is True

    async def test_failure_unavailable_marks_degraded(self):
        p = _processor(_Provider(error=DocumentContextProviderUnavailableException("u")))
        st = _state()
        await p.run(st)
        assert st.retrieval_degraded is True

    async def test_run_applies_char_budget(self, make_fragment):
        frs = [make_fragment(fragment_id=i + 1, content="y" * 400) for i in range(5)]
        p = _processor(_Provider(fragments=frs), max_fragments=50, max_context_chars=1_000)
        st = _state()
        await p.run(st)
        assert len(st.fragments) == 2
