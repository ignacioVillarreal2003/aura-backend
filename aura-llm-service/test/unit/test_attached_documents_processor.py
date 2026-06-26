import types

from app.application.services.generation_shared.processors.attached_documents_processor.attached_documents_processor import (
    AttachedDocumentsProcessor,
)
from app.application.services.generation_shared.processors.attached_documents_processor.attached_documents_settings import (
    AttachedDocumentsSettings,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


class _Provider:
    def __init__(self, fragments=None, boom=False):
        self._fragments = fragments or []
        self._boom = boom

    async def retrieve_context_fragments_by_document(self, authenticated_user, document_ids):
        if self._boom:
            raise RuntimeError("context service down")
        return types.SimpleNamespace(fragments=self._fragments)


def _processor(provider, **overrides) -> AttachedDocumentsProcessor:
    return AttachedDocumentsProcessor(provider, AttachedDocumentsSettings(**overrides))


def _state(document_ids) -> GenerationState:
    st = GenerationState.create(
        messages=[Message(role=MessageRole.human, content="pregunta")],
        chat_id=1, retrieve_context=False, authenticated_user=types.SimpleNamespace(id=7),
        document_ids=document_ids,
    )
    return st


class TestHelpers:
    def test_unique_document_ids_preserves_order(self):
        p = _processor(_Provider())
        assert p._unique_document_ids([3, 1, 3, 2, 1]) == [3, 1, 2]

    def test_round_robin_visits_requested_order_then_interleaves(self, make_fragment):
        p = _processor(_Provider())
        frs = (
            [make_fragment(fragment_id=i + 1, document_id=1, fragment_index=i) for i in range(3)]
            + [make_fragment(fragment_id=10, document_id=2, fragment_index=0)]
        )
        ordered = p._round_robin_by_document(frs, requested_ids=[2, 1])
        head = [(f.document_id, f.fragment_index) for f in ordered[:2]]
        assert head == [(2, 0), (1, 0)]

    def test_budget_count_keeps_documents_represented(self, make_fragment):
        p = _processor(_Provider(), max_fragments=4)
        frs = (
            [make_fragment(fragment_id=i + 1, document_id=1, fragment_index=i) for i in range(5)]
            + [make_fragment(fragment_id=10, document_id=2, fragment_index=0)]
            + [make_fragment(fragment_id=20, document_id=3, fragment_index=0)]
        )
        selected = p._select_fragments(frs, requested_ids=[1, 2, 3])
        assert len(selected) == 4
        assert {f.document_id for f in selected} == {1, 2, 3}

    def test_char_budget_drops_whole_fragments(self, make_fragment):
        p = _processor(_Provider(), max_chars=500, fair_distribution=False)
        frs = [make_fragment(fragment_id=i + 1, content="y" * 200) for i in range(5)]
        selected = p._apply_budget(frs)
        assert len(selected) == 2

    def test_char_budget_keeps_at_least_one(self, make_fragment):
        p = _processor(_Provider(), max_chars=500, fair_distribution=False)
        selected = p._apply_budget([make_fragment(content="z" * 5_000)])
        assert len(selected) == 1


class TestRun:
    async def test_run_success(self, make_fragment):
        frs = [make_fragment(fragment_id=i + 1, document_id=1, fragment_index=i) for i in range(3)]
        p = _processor(_Provider(fragments=frs))
        st = _state([1])
        await p.run(st)
        assert len(st.attached_fragments) == 3 and st.attached_degraded is False

    async def test_run_marks_degraded_on_fetch_failure(self):
        p = _processor(_Provider(boom=True))
        st = _state([1, 2])
        await p.run(st)
        assert st.attached_fragments == [] and st.attached_degraded is True

    async def test_run_noop_without_document_ids(self):
        p = _processor(_Provider())
        st = _state([])
        await p.run(st)
        assert st.attached_fragments == [] and st.attached_degraded is False

    async def test_run_handles_unexpected_payload(self):
        class _Bad:
            async def retrieve_context_fragments_by_document(self, authenticated_user, document_ids):
                return types.SimpleNamespace(fragments=None)

        p = _processor(_Bad())
        st = _state([1])
        await p.run(st)
        assert st.attached_fragments == [] and st.attached_degraded is False
