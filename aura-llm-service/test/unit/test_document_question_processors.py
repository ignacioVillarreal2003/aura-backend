from app.application.services.user_interactions.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.application.services.user_interactions.document_question_service.document_question_state import (
    DocumentQuestionState,
)
from app.application.services.user_interactions.document_question_service.processors.answer_document_question_processor.answer_document_question_processor import (
    AnswerDocumentQuestionProcessor,
)
from app.application.services.user_interactions.document_question_service.processors.context_document_question_processor.context_document_question_processor import (
    _build_question_context_fragments_request,
)
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


def _state(history=False, base_question=None, keyword_question=None) -> DocumentQuestionState:
    messages = [Message(role=MessageRole.human, content="¿Qué dice el artículo 12?")]
    if history:
        messages = [
            Message(role=MessageRole.human, content="¿Qué es el reglamento?"),
            Message(role=MessageRole.assistant, content="Es..."),
            *messages,
        ]
    state = DocumentQuestionState(messages=messages, authenticated_user=None, chat_id=1)
    state.base_question = base_question
    state.keyword_question = keyword_question
    return state


class TestQuestionRetrievalRequest:
    def test_single_turn_still_gets_bm25_lane(self):
        request = _build_question_context_fragments_request(
            _state(), DocumentQuestionServiceSettings()
        )
        assert len(request.bm25_queries) == 1
        assert request.bm25_queries[0].text == "¿Qué dice el artículo 12?"

    def test_multi_turn_adds_base_question_as_second_bm25_lane(self):
        request = _build_question_context_fragments_request(
            _state(history=True, base_question="¿Qué dice el artículo 12 del reglamento?"),
            DocumentQuestionServiceSettings(),
        )
        assert [q.text for q in request.bm25_queries] == [
            "¿Qué dice el artículo 12?",
            "¿Qué dice el artículo 12 del reglamento?",
        ]

    def test_keywords_add_semantic_lane(self):
        request = _build_question_context_fragments_request(
            _state(keyword_question="artículo 12 reglamento"),
            DocumentQuestionServiceSettings(),
        )
        assert request.semantic_queries[-1].text == "artículo 12 reglamento"

    def test_dual_bm25_disabled_removes_lanes(self):
        request = _build_question_context_fragments_request(
            _state(), DocumentQuestionServiceSettings(enable_dual_bm25=False)
        )
        assert request.bm25_queries == []


class TestAnswerContextBuilding:
    def _build_input(self, state):
        return AnswerDocumentQuestionProcessor.build_llm_input(
            document_question_state=state,
            history_messages_window=4,
            max_context_chars=10_000,
        )

    def test_context_includes_document_names(self, make_fragment):
        state = _state()
        state.attached_fragments = [
            make_fragment(content="texto del fragmento", document_name="Reglamento X")
        ]
        human = self._build_input(state)[-1]
        assert "[Reglamento X]" in human.content
        assert "texto del fragmento" in human.content

    def test_reduced_context_replaces_attached_but_keeps_rag(self, make_fragment):
        state = _state()
        state.attached_fragments = [make_fragment(fragment_id=1, content="adjunto crudo")]
        state.fragments = [
            make_fragment(fragment_id=2, content="fragmento rag", document_name="Otro Doc")
        ]
        state.reduced_attached_context = "resumen del adjunto"
        human = self._build_input(state)[-1]
        assert "resumen del adjunto" in human.content
        assert "adjunto crudo" not in human.content
        assert "[Otro Doc]" in human.content

    def test_operator_prompt_and_style_are_applied(self):
        state = _state()
        state.fragments = []
        state.reduced_attached_context = "contexto"
        state.system_prompt = "Indicación del operador."
        state.response_style = "Tono breve."
        system = self._build_input(state)[0]
        assert "Indicación del operador." in system.content
        assert "Tono breve." in system.content
