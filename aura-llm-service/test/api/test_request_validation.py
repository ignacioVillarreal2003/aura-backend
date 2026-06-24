"""
Unit tests for Pydantic request DTOs.
Each model is tested in isolation — no HTTP layer, no mocks.
"""
import pytest
from pydantic import ValidationError

from app.domain.dtos.user_interactions.agent.agent_request import AgentRequest
from app.domain.dtos.user_interactions.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.processing.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.user_interactions.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.user_interactions.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.processing.fragment_contextualize.contextualize_fragment_request import (
    ContextualizeFragmentRequest,
)
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_request import ExtractEntitiesRelationsRequest
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_request import (
    GraphOntology,
    TranslateGraphQueryRequest,
)

_HUMAN_MSG = {"role": "human", "content": "¿Qué dice el documento?"}
_AI_MSG = {"role": "assistant", "content": "Aquí está la respuesta."}



class TestDocumentQuestionRequest:
    def test_valid_single_human_message(self):
        req = DocumentQuestionRequest(messages=[_HUMAN_MSG], chat_id=1)
        assert req.messages[0].role.value == "human"

    def test_valid_with_history(self):
        req = DocumentQuestionRequest(messages=[_HUMAN_MSG, _AI_MSG, _HUMAN_MSG], chat_id=1)
        assert len(req.messages) == 3

    def test_last_message_must_be_human(self):
        with pytest.raises(ValidationError):
            DocumentQuestionRequest(messages=[_HUMAN_MSG, _AI_MSG], chat_id=1)

    def test_empty_messages_raises(self):
        with pytest.raises(ValidationError):
            DocumentQuestionRequest(messages=[], chat_id=1)

    def test_blank_message_content_raises(self):
        with pytest.raises(ValidationError):
            DocumentQuestionRequest(messages=[{"role": "human", "content": "   "}], chat_id=1)

    def test_missing_chat_id_raises(self):
        with pytest.raises(ValidationError):
            DocumentQuestionRequest(messages=[_HUMAN_MSG])

    def test_valid_chat_id(self):
        req = DocumentQuestionRequest(messages=[_HUMAN_MSG], chat_id=5)
        assert req.chat_id == 5

    def test_zero_chat_id_raises(self):
        with pytest.raises(ValidationError):
            DocumentQuestionRequest(messages=[_HUMAN_MSG], chat_id=0)



class TestClassifyDocumentRequest:
    def test_valid_request(self):
        req = ClassifyDocumentRequest(document_name="contrato.pdf", content="Contenido del documento.")
        assert req.document_name == "contrato.pdf"

    def test_blank_document_name_raises(self):
        with pytest.raises(ValidationError):
            ClassifyDocumentRequest(document_name="   ", content="Contenido.")

    def test_blank_content_raises(self):
        with pytest.raises(ValidationError):
            ClassifyDocumentRequest(document_name="doc.pdf", content="   ")

    def test_empty_document_name_raises(self):
        with pytest.raises(ValidationError):
            ClassifyDocumentRequest(document_name="", content="Contenido.")

    def test_strips_whitespace_from_fields(self):
        req = ClassifyDocumentRequest(document_name="  doc.pdf  ", content="  Texto.  ")
        assert req.document_name == "doc.pdf"
        assert req.content == "Texto."

    def test_content_exceeding_max_length_raises(self):
        with pytest.raises(ValidationError):
            ClassifyDocumentRequest(document_name="doc.pdf", content="x" * 50_001)



class TestDocumentSummaryRequest:
    def test_valid_single_document_id(self):
        req = DocumentSummaryRequest(document_ids=[1], chat_id=1)
        assert req.document_ids == [1]

    def test_valid_multiple_ids(self):
        req = DocumentSummaryRequest(document_ids=[1, 2, 3], chat_id=1)
        assert len(req.document_ids) == 3

    def test_missing_chat_id_raises(self):
        with pytest.raises(ValidationError):
            DocumentSummaryRequest(document_ids=[1])

    def test_empty_list_raises(self):
        with pytest.raises(ValidationError):
            DocumentSummaryRequest(document_ids=[], chat_id=1)

    def test_duplicate_ids_raise(self):
        with pytest.raises(ValidationError):
            DocumentSummaryRequest(document_ids=[1, 1, 2], chat_id=1)

    def test_zero_id_raises(self):
        with pytest.raises(ValidationError):
            DocumentSummaryRequest(document_ids=[0], chat_id=1)

    def test_negative_id_raises(self):
        with pytest.raises(ValidationError):
            DocumentSummaryRequest(document_ids=[-1], chat_id=1)

    def test_too_many_ids_raises(self):
        with pytest.raises(ValidationError):
            DocumentSummaryRequest(document_ids=list(range(1, 52)), chat_id=1)



class TestAgentRequest:
    def test_valid_single_human_message(self):
        req = AgentRequest(messages=[_HUMAN_MSG], chat_id=1)
        assert len(req.messages) == 1

    def test_last_message_must_be_human(self):
        with pytest.raises(ValidationError):
            AgentRequest(messages=[_HUMAN_MSG, _AI_MSG], chat_id=1)

    def test_empty_messages_raises(self):
        with pytest.raises(ValidationError):
            AgentRequest(messages=[], chat_id=1)

    def test_missing_chat_id_raises(self):
        with pytest.raises(ValidationError):
            AgentRequest(messages=[_HUMAN_MSG])

    def test_multi_turn_ends_with_human(self):
        req = AgentRequest(messages=[_HUMAN_MSG, _AI_MSG, _HUMAN_MSG], chat_id=1)
        assert req.messages[-1].role.value == "human"



class TestDocumentActionRequest:
    def test_valid_request(self):
        req = DocumentActionRequest(document_ids=[1, 2], instruction="Resumir el contenido.", chat_id=1)
        assert req.instruction == "Resumir el contenido."

    def test_missing_chat_id_raises(self):
        with pytest.raises(ValidationError):
            DocumentActionRequest(document_ids=[1], instruction="Resumir.")

    def test_blank_instruction_raises(self):
        with pytest.raises(ValidationError):
            DocumentActionRequest(document_ids=[1], instruction="   ", chat_id=1)

    def test_duplicate_document_ids_raise(self):
        with pytest.raises(ValidationError):
            DocumentActionRequest(document_ids=[1, 1], instruction="Resumir.", chat_id=1)

    def test_zero_document_id_raises(self):
        with pytest.raises(ValidationError):
            DocumentActionRequest(document_ids=[0], instruction="Resumir.", chat_id=1)

    def test_empty_document_ids_raises(self):
        with pytest.raises(ValidationError):
            DocumentActionRequest(document_ids=[], instruction="Resumir.", chat_id=1)

    def test_strips_whitespace_from_instruction(self):
        req = DocumentActionRequest(document_ids=[1], instruction="  Resumir.  ", chat_id=1)
        assert req.instruction == "Resumir."

    def test_optional_action_defaults_to_none(self):
        req = DocumentActionRequest(document_ids=[1], instruction="Resumir.", chat_id=1)
        assert req.action is None



class TestContextualizeFragmentRequest:
    def test_valid_request(self):
        req = ContextualizeFragmentRequest(
            document_summary="Resumen del documento.",
            content="Fragmento de texto del documento.",
        )
        assert req.content == "Fragmento de texto del documento."
        assert req.document_summary == "Resumen del documento."

    def test_blank_content_raises(self):
        with pytest.raises(ValidationError):
            ContextualizeFragmentRequest(document_summary="Resumen.", content="   ")

    def test_empty_content_raises(self):
        with pytest.raises(ValidationError):
            ContextualizeFragmentRequest(document_summary="Resumen.", content="")

    def test_blank_document_summary_raises(self):
        with pytest.raises(ValidationError):
            ContextualizeFragmentRequest(document_summary="   ", content="Texto.")

    def test_strips_whitespace(self):
        req = ContextualizeFragmentRequest(document_summary="  Resumen.  ", content="  Texto.  ")
        assert req.content == "Texto."
        assert req.document_summary == "Resumen."

    def test_content_exceeding_max_raises(self):
        with pytest.raises(ValidationError):
            ContextualizeFragmentRequest(document_summary="Resumen.", content="x" * 50_001)



class TestExtractEntitiesRelationsRequest:
    def test_valid_request(self):
        req = ExtractEntitiesRelationsRequest(
            content="Texto del fragmento.",
            document_id=1,
            fragment_id=1,
            allowed_entity_types=["PERSON", "ORGANIZATION"],
        )
        assert req.document_id == 1

    def test_empty_allowed_entity_types_raises(self):
        with pytest.raises(ValidationError):
            ExtractEntitiesRelationsRequest(
                content="Texto.",
                document_id=1,
                fragment_id=1,
                allowed_entity_types=[],
            )

    def test_blank_entity_type_raises(self):
        with pytest.raises(ValidationError):
            ExtractEntitiesRelationsRequest(
                content="Texto.",
                document_id=1,
                fragment_id=1,
                allowed_entity_types=["  "],
            )

    def test_zero_document_id_raises(self):
        with pytest.raises(ValidationError):
            ExtractEntitiesRelationsRequest(
                content="Texto.",
                document_id=0,
                fragment_id=1,
                allowed_entity_types=["PERSON"],
            )

    def test_optional_relation_types_defaults_to_none(self):
        req = ExtractEntitiesRelationsRequest(
            content="Texto.",
            document_id=1,
            fragment_id=1,
            allowed_entity_types=["PERSON"],
        )
        assert req.allowed_relation_types is None



class TestTranslateGraphQueryRequest:
    def test_valid_request(self):
        req = TranslateGraphQueryRequest(
            question="¿Quién firmó el contrato?",
            ontology=GraphOntology(entity_types=["PERSON", "ORGANIZATION"]),
        )
        assert req.question == "¿Quién firmó el contrato?"

    def test_empty_question_raises(self):
        with pytest.raises(ValidationError):
            TranslateGraphQueryRequest(
                question="",
                ontology=GraphOntology(entity_types=["PERSON"]),
            )

    def test_empty_entity_types_in_ontology_raises(self):
        with pytest.raises(ValidationError):
            TranslateGraphQueryRequest(
                question="¿Quién?",
                ontology=GraphOntology(entity_types=[]),
            )

    def test_blank_entity_type_raises(self):
        with pytest.raises(ValidationError):
            TranslateGraphQueryRequest(
                question="¿Quién?",
                ontology=GraphOntology(entity_types=["  "]),
            )

    def test_relation_types_default_to_empty(self):
        req = TranslateGraphQueryRequest(
            question="¿Quién firmó?",
            ontology=GraphOntology(entity_types=["PERSON"]),
        )
        assert req.ontology.relation_types == []
