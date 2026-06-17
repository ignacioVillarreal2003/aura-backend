from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_utils import (
    format_history_messages,
)
from app.application.services.generation_shared.processors.context_retrieval_processor.context_retrieval_processor import (
    ContextRetrievalProcessor,
)
from app.application.services.generation_shared.processors.context_retrieval_processor.context_retrieval_settings import (
    ContextRetrievalSettings,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


class TestFormatHistoryMessages:
    def test_keeps_only_the_last_window_messages(self):
        history = [Message(role=MessageRole.human, content=f"m{i}") for i in range(6)]
        formatted = format_history_messages(2, history)
        assert formatted == "Usuario: m4\nUsuario: m5"

    def test_zero_window_returns_empty(self):
        history = [Message(role=MessageRole.human, content="m0")]
        assert format_history_messages(0, history) == ""

    def test_roles_are_labelled(self):
        history = [
            Message(role=MessageRole.human, content="pregunta"),
            Message(role=MessageRole.assistant, content="respuesta"),
        ]
        formatted = format_history_messages(4, history)
        assert formatted == "Usuario: pregunta\nAsistente: respuesta"


def _retrieval_state(base_question=None, keyword_question=None) -> GenerationState:
    state = GenerationState.create(
        messages=[Message(role=MessageRole.human, content="pregunta original")],
        chat_id=7,
        retrieve_context=True,
        authenticated_user=None,
    )
    state.base_question = base_question
    state.keyword_question = keyword_question
    return state


class TestContextRetrievalRequestBuilding:
    def _build(self, state, **settings_overrides):
        settings = ContextRetrievalSettings(**settings_overrides)
        processor = ContextRetrievalProcessor(document_context_provider=None,
                                              context_retrieval_settings=settings)
        return processor._build_request(state)

    def test_only_original_lane_when_no_base_or_keywords(self):
        request = self._build(_retrieval_state())
        assert [q.text for q in request.semantic_queries] == ["pregunta original"]
        assert [q.text for q in request.bm25_queries] == ["pregunta original"]

    def test_lanes_for_original_base_and_keywords(self):
        request = self._build(
            _retrieval_state(base_question="reformulada", keyword_question="kw1 kw2"),
        )
        expected = ["pregunta original", "reformulada", "kw1 kw2"]
        assert [q.text for q in request.semantic_queries] == expected
        assert [q.text for q in request.bm25_queries] == expected

    def test_deduplicates_when_base_equals_original(self):
        request = self._build(_retrieval_state(base_question="pregunta original"))
        assert [q.text for q in request.semantic_queries] == ["pregunta original"]
        assert [q.text for q in request.bm25_queries] == ["pregunta original"]

    def test_rerank_capped_by_pool(self):
        request = self._build(
            _retrieval_state(),
            semantic_fragments_per_lane=1,
            bm25_fragments_per_lane=1,
            max_fragments=50,
        )
        assert request.rerank.enabled is True
        assert request.rerank.max_fragments <= 2

    def test_rerank_disabled_by_settings(self):
        request = self._build(_retrieval_state(), use_rerank=False)
        assert request.rerank.enabled is False
