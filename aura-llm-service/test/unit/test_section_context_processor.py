import pytest

from app.application.services.generation_shared.processors.section_context_processor.section_context_processor import (
    SectionContextProcessor,
)
from app.application.services.generation_shared.processors.section_context_processor.section_context_settings import (
    SectionContextSettings,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.dtos.fragment_list_response import FragmentSectionGroup


class _FakeLLM:
    def bind(self, **_kwargs):
        return self


class _FakeFacade:
    async def get_llm_base(self):
        return _FakeLLM()


class _BoomFacade:
    async def get_llm_base(self):
        raise RuntimeError("llm unavailable")


class _Invoker:
    def __init__(self, text="NOTA", boom=False):
        self._text = text
        self._boom = boom
        self.calls = 0

    async def call_llm_content(self, llm, llm_input):
        self.calls += 1
        if self._boom:
            raise RuntimeError("llm down")
        return self._text


def _frag(make_fragment, fragment_id, content, section="Sección A", idx=0):
    return make_fragment(
        fragment_id=fragment_id,
        content=content,
        fragment_index=idx,
        section_path=section,
    )


def _group(make_fragment, primary_id, secondary_sizes, section="Sección A"):
    primary = _frag(make_fragment, primary_id, "primario", section=section, idx=0)
    secondary = [
        _frag(make_fragment, primary_id * 100 + i, "y" * size, section=section, idx=i + 1)
        for i, size in enumerate(secondary_sizes)
    ]
    return FragmentSectionGroup(primary=primary, section_fragments=secondary)


def _state(groups) -> GenerationState:
    st = GenerationState.create(
        messages=[Message(role=MessageRole.human, content="pregunta")],
        chat_id=1, retrieve_context=True, authenticated_user=None,
    )
    st.section_groups = groups
    return st


def _settings(**overrides) -> SectionContextSettings:
    base = dict(summarize_threshold_chars=500, max_section_context_chars=500, max_concurrent_groups=4)
    base.update(overrides)
    return SectionContextSettings(**base)


class TestIsNeeded:
    def test_no_groups_not_needed(self):
        p = SectionContextProcessor(_FakeFacade(), _Invoker(), _settings())
        assert p.is_needed(_state(None)) is False

    def test_below_threshold_not_needed(self, make_fragment):
        p = SectionContextProcessor(_FakeFacade(), _Invoker(), _settings(summarize_threshold_chars=10_000))
        assert p.is_needed(_state([_group(make_fragment, 1, [100, 100])])) is False

    def test_above_threshold_needed(self, make_fragment):
        p = SectionContextProcessor(_FakeFacade(), _Invoker(), _settings(summarize_threshold_chars=500))
        assert p.is_needed(_state([_group(make_fragment, 1, [600])])) is True


class TestRun:
    async def test_no_groups_is_noop(self):
        invoker = _Invoker()
        p = SectionContextProcessor(_FakeFacade(), invoker, _settings())
        state = _state(None)
        await p.run(state)
        assert state.section_summary is None
        assert invoker.calls == 0

    async def test_below_threshold_keeps_verbatim(self, make_fragment):
        invoker = _Invoker()
        p = SectionContextProcessor(_FakeFacade(), invoker, _settings(summarize_threshold_chars=10_000))
        state = _state([_group(make_fragment, 1, [100])])
        await p.run(state)
        assert state.section_summary is None
        assert invoker.calls == 0

    async def test_above_threshold_summarizes_and_caps(self, make_fragment):
        invoker = _Invoker(text="z" * 1_000)
        p = SectionContextProcessor(
            _FakeFacade(), invoker, _settings(summarize_threshold_chars=500, max_section_context_chars=500)
        )
        state = _state([_group(make_fragment, 1, [600])])
        await p.run(state)
        assert state.section_summary is not None
        assert invoker.calls == 1
        assert len(state.section_summary) <= 500

    async def test_per_group_failure_falls_back_to_verbatim(self, make_fragment):
        invoker = _Invoker(boom=True)
        p = SectionContextProcessor(_FakeFacade(), invoker, _settings(summarize_threshold_chars=500))
        state = _state([_group(make_fragment, 1, [600])])
        await p.run(state)
        assert state.section_summary is None

    async def test_llm_build_failure_marks_degraded(self, make_fragment):
        p = SectionContextProcessor(_BoomFacade(), _Invoker(), _settings(summarize_threshold_chars=500))
        state = _state([_group(make_fragment, 1, [600])])
        await p.run(state)
        assert state.section_summary is None
        assert state.reduction_degraded is True
