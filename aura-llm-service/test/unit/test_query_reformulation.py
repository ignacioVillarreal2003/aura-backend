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
        is_rag=True,
        authenticated_user=None,
    )
    state.base_question = base_question
    state.keyword_question = keyword_question
    return state


class TestContextRetrievalRequestBuilding:
    def _build(self, state, queries=None, **settings_overrides):
        settings = ContextRetrievalSettings(**settings_overrides)
        processor = ContextRetrievalProcessor(document_context_provider=None,
                                              context_retrieval_settings=settings)
        return processor._build_request(state, queries or [])

    def test_semantic_lane_per_rag_query_plus_keywords(self):
        request = self._build(
            _retrieval_state(keyword_question="kw1 kw2"),
            queries=["tema A", "tema B"],
        )
        texts = [q.text for q in request.semantic_queries]
        assert texts == ["pregunta original tema A", "pregunta original tema B", "kw1 kw2"]

    def test_base_question_replaces_original_when_present(self):
        request = self._build(_retrieval_state(base_question="reformulada"), queries=["q"])
        assert request.semantic_queries[0].text == "reformulada q"
        assert request.bm25_queries[0].text == "reformulada"

    def test_bm25_adds_keywords_lane_when_different(self):
        request = self._build(_retrieval_state(keyword_question="kw"))
        assert [q.text for q in request.bm25_queries] == ["pregunta original", "kw"]

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
