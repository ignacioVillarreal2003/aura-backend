from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.application.services.generation_shared.generation_messages import (
    build_context_block,
    build_generation_messages,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


def _state(messages=None) -> GenerationState:
    return GenerationState.create(
        messages=messages
        or [
            Message(role=MessageRole.human, content="m1"),
            Message(role=MessageRole.assistant, content="m2"),
            Message(role=MessageRole.human, content="pregunta actual"),
        ],
        chat_id=1,
        is_rag=True,
        authenticated_user=None,
    )


class TestBuildContextBlock:
    def test_no_fragments_returns_placeholder(self):
        block = build_context_block(_state(), max_context_chars=1000)
        assert "Sin contexto documental" in block

    def test_reduced_context_takes_precedence(self, make_fragment):
        state = _state()
        state.reduced_context = "síntesis previa"
        state.attached_fragments = [make_fragment()]
        block = build_context_block(state, max_context_chars=1000)
        assert "síntesis previa" in block
        assert "SÍNTESIS DE CONTEXTO" in block

    def test_attached_section_marked_as_priority(self, make_fragment):
        state = _state()
        state.attached_fragments = [make_fragment(content="contenido adjunto")]
        block = build_context_block(state, max_context_chars=1000)
        assert "FUENTE PRIORITARIA" in block
        assert "contenido adjunto" in block

    def test_fragment_header_includes_document_name(self, make_fragment):
        state = _state()
        state.fragments = [make_fragment(document_name="Reglamento X", content="dato")]
        block = build_context_block(state, max_context_chars=1000)
        assert "Reglamento X" in block

    def test_budget_limits_rag_fragments(self, make_fragment):
        state = _state()
        state.fragments = [
            make_fragment(fragment_id=1, content="a" * 400),
            make_fragment(fragment_id=2, content="b" * 400),
        ]
        block = build_context_block(state, max_context_chars=500)
        assert "a" * 400 in block
        assert "b" * 400 not in block

    def test_attached_reserve_splits_budget_when_rag_present(self, make_fragment):
        state = _state()
        state.attached_fragments = [make_fragment(fragment_id=1, content="x" * 800)]
        state.fragments = [make_fragment(fragment_id=2, content="y" * 200)]
        block = build_context_block(state, max_context_chars=1000, attached_reserve_ratio=0.6)
        # The attached fragment (800 chars) exceeds its 600-char reserve and is dropped,
        # while the rag fragment fits in the remainder.
        assert "x" * 800 not in block
        assert "y" * 200 in block


class TestBuildGenerationMessages:
    def test_structure_system_history_human(self):
        messages = build_generation_messages(
            "system", "{context}|{input}", _state(), history_messages_window=4, context_block="CTX"
        )
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage) and messages[1].content == "m1"
        assert isinstance(messages[2], AIMessage) and messages[2].content == "m2"
        assert messages[-1].content == "CTX|pregunta actual"

    def test_window_keeps_only_last_messages(self):
        many = [
            Message(role=MessageRole.human, content=f"h{i}") for i in range(5)
        ] + [Message(role=MessageRole.human, content="actual")]
        messages = build_generation_messages(
            "system", "{context}|{input}", _state(many), history_messages_window=2, context_block="C"
        )
        # system + 2 history + final human
        assert len(messages) == 4
        assert messages[1].content == "h3"

    def test_zero_window_drops_history(self):
        messages = build_generation_messages(
            "system", "{context}|{input}", _state(), history_messages_window=0, context_block="C"
        )
        assert len(messages) == 2
