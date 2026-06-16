from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


def _state(**overrides) -> GenerationState:
    defaults = dict(
        messages=[
            Message(role=MessageRole.human, content="primera"),
            Message(role=MessageRole.assistant, content="respuesta"),
            Message(role=MessageRole.human, content="actual"),
        ],
        chat_id=1,
        retrieve_context=True,
        authenticated_user=None,
    )
    defaults.update(overrides)
    return GenerationState.create(**defaults)


class TestGenerationState:
    def test_current_message_is_last(self):
        assert _state().current_message.content == "actual"

    def test_history_excludes_current(self):
        history = _state().history_messages
        assert [m.content for m in history] == ["primera", "respuesta"]

    def test_rag_only_fragments_deduplicates_attached(self, make_fragment):
        state = _state()
        state.attached_fragments = [make_fragment(fragment_id=1)]
        state.fragments = [make_fragment(fragment_id=1), make_fragment(fragment_id=2)]
        assert [f.id for f in state.rag_only_fragments] == [2]

    def test_all_fragments_puts_attached_first(self, make_fragment):
        state = _state()
        state.attached_fragments = [make_fragment(fragment_id=5)]
        state.fragments = [make_fragment(fragment_id=9)]
        assert [f.id for f in state.all_fragments] == [5, 9]
