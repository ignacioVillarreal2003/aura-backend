import asyncio

import pytest

from app.application.services.generation_shared.processors.context_reduction_processor.context_reduction_processor import (
    ContextReductionProcessor,
    _ReductionPrompts,
)
from app.application.services.generation_shared.processors.context_reduction_processor.context_reduction_settings import (
    ContextReductionSettings,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


_PROMPTS = _ReductionPrompts("ms", "{query}|{fragments}", "rs", "{query}|{fragments}")


class _FakeLLM:
    def bind(self, **_kwargs):
        return self


class _FakeFacade:
    async def get_llm_base(self):
        return _FakeLLM()


class _Invoker:
    """Configurable fake: transform(text) -> str, or raise when boom=True."""

    def __init__(self, transform=lambda t: "ok", boom=False, delay=0.0):
        self._transform = transform
        self._boom = boom
        self._delay = delay

    async def call_llm_content(self, llm, llm_input):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._boom:
            raise RuntimeError("llm down")
        return self._transform(llm_input[-1].content)


def _settings(**overrides) -> ContextReductionSettings:
    base = dict(
        max_batch_chars=1_000,
        max_batch_tokens=256,
        max_passes=5,
        max_context_chars=1_000,
        max_concurrent_batches=4,
        deadline_seconds=30.0,
    )
    base.update(overrides)
    return ContextReductionSettings(**base)


def _processor(invoker, **overrides) -> ContextReductionProcessor:
    return ContextReductionProcessor(_FakeFacade(), invoker, _settings(**overrides))


def _units(count: int, size: int) -> list[str]:
    return ["[D] " + "x" * size for _ in range(count)]


class TestBudgetingHelpers:
    def test_batch_budget_is_min_of_chars_and_token_ceiling(self):
        p = _processor(_Invoker(), max_batch_chars=20_000, max_batch_tokens=256)
        assert p._batch_char_budget() == 1_024

    def test_batch_budget_chars_wins_when_smaller(self):
        p = _processor(_Invoker(), max_batch_chars=1_000, max_batch_tokens=256)
        assert p._batch_char_budget() == 1_000

    def test_fragment_units_never_exceed_budget_including_label(self, make_fragment):
        p = _processor(_Invoker())
        frag = make_fragment(content="A" * 5_000, document_name="DocumentoConNombreLargo")
        units = p._fragment_units([frag])
        assert units and all(len(u) <= p._batch_char_budget() for u in units)

    def test_batches_respect_budget_including_separators(self):
        p = _processor(_Invoker())
        units = _units(5, 400)
        for batch in p._batches(units):
            assert len("\n\n".join(batch)) <= p._batch_char_budget()

    def test_fit_notes_drops_whole_notes_instead_of_cutting(self):
        p = _processor(_Invoker(), max_context_chars=1_000)
        notes = ["x" * 600, "y" * 600, "z" * 600]
        fit = p._fit_notes(notes)
        assert "y" * 600 not in fit and "z" * 600 not in fit
        assert len(fit) <= 1_000

    def test_fit_notes_keeps_at_least_one_note(self):
        p = _processor(_Invoker(), max_context_chars=1_000)
        fit = p._fit_notes(["a" * 5_000])
        assert len(fit) == 1_000


class TestIsNeeded:
    def _state(self, fragments) -> GenerationState:
        st = GenerationState.create(
            messages=[Message(role=MessageRole.human, content="pregunta")],
            chat_id=1, retrieve_context=True, authenticated_user=None,
        )
        st.fragments = fragments
        return st

    def test_not_needed_when_under_budget(self, make_fragment):
        p = _processor(_Invoker(), max_context_chars=10_000)
        assert p.is_needed(self._state([make_fragment(content="x" * 100)])) is False

    def test_needed_when_over_budget(self, make_fragment):
        p = _processor(_Invoker(), max_context_chars=1_000)
        assert p.is_needed(self._state([make_fragment(content="x" * 5_000)])) is True

    def test_not_needed_without_fragments(self):
        p = _processor(_Invoker())
        assert p.is_needed(self._state([])) is False


class TestReduceOutcomes:
    async def test_fit(self):
        p = _processor(_Invoker(transform=lambda t: "ok"))
        r = await p._reduce(llm=None, fragments=_units(4, 800), query="q", prompts=_PROMPTS)
        assert r.outcome == "fit" and not r.degraded and r.text == "\n\n".join(["ok"] * 4)

    async def test_converged_single_batch_over_budget(self):
        p = _processor(_Invoker(transform=lambda t: t * 2))
        r = await p._reduce(llm=None, fragments=["[D] " + "a" * 500], query="q", prompts=_PROMPTS)
        assert r.outcome == "converged" and r.degraded

    async def test_not_shrinking(self):
        p = _processor(_Invoker(transform=lambda t: t))
        r = await p._reduce(llm=None, fragments=_units(4, 900), query="q", prompts=_PROMPTS)
        assert r.outcome == "not_shrinking" and r.degraded and r.passes_used == 2

    async def test_exhausted(self):
        p = _processor(_Invoker(transform=lambda t: t), max_passes=1)
        r = await p._reduce(llm=None, fragments=_units(4, 900), query="q", prompts=_PROMPTS)
        assert r.outcome == "exhausted" and r.degraded and r.passes_used == 1

    async def test_empty_and_failed_batches_counted(self):
        p = _processor(_Invoker(boom=True))
        r = await p._reduce(llm=None, fragments=_units(3, 900), query="q", prompts=_PROMPTS)
        assert r.outcome == "empty" and r.degraded and r.text == "" and r.failed_batches == 3

    async def test_timeout_returns_best_so_far(self):
        p = _processor(_Invoker(transform=lambda t: t, delay=0.05), deadline_seconds=0.01)
        r = await p._reduce(llm=None, fragments=_units(4, 900), query="q", prompts=_PROMPTS)
        assert r.outcome == "timeout" and r.degraded and r.text


class TestRun:
    def _state(self, fragments) -> GenerationState:
        st = GenerationState.create(
            messages=[Message(role=MessageRole.human, content="pregunta")],
            chat_id=1, retrieve_context=True, authenticated_user=None,
        )
        st.fragments = fragments
        return st

    async def test_run_sets_reduced_context_on_success(self, make_fragment):
        p = _processor(_Invoker(transform=lambda t: "ok"))
        st = self._state([make_fragment(content="x" * 5_000)])
        await p.run(st)
        assert st.reduced_context and "ok" in st.reduced_context and st.reduction_degraded is False

    async def test_run_marks_degraded_on_total_failure(self, make_fragment):
        p = _processor(_Invoker(boom=True))
        st = self._state([make_fragment(content="x" * 5_000)])
        await p.run(st)
        assert st.reduced_context is None and st.reduction_degraded is True

    async def test_run_noop_when_not_needed(self, make_fragment):
        p = _processor(_Invoker(transform=lambda t: "ok"), max_context_chars=50_000)
        st = self._state([make_fragment(content="x" * 100)])
        await p.run(st)
        assert st.reduced_context is None and st.reduction_degraded is False
