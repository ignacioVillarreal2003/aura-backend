"""Unit tests locking in the domain-request hardening:
- optional operator prompts (system_prompt/response_style) are normalized
  (control chars stripped, blank -> None);
- requests reject unknown fields (extra="forbid");
- attached document_ids share the MAX_DOCUMENT_IDS_PER_REQUEST (50) ceiling;
- graph DTOs validate type lengths via field validators.
"""
import pytest
from pydantic import ValidationError

from app.domain.field_limits import MAX_DOCUMENT_IDS_PER_REQUEST
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_request import (
    ExtractEntitiesRelationsRequest,
)
from app.domain.dtos.processing.graph_query_translation.translate_graph_query_request import (
    GraphOntology,
    TranslateGraphQueryRequest,
)
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.general_chat.general_chat_request import GeneralChatRequest
from app.domain.validation import normalize_optional_prompt

_HUMAN = {"role": "human", "content": "hola"}


def _chat(**overrides) -> dict:
    base = {"messages": [_HUMAN], "chat_id": 1}
    base.update(overrides)
    return base


class TestOptionalPromptNormalization:
    def test_whitespace_only_prompt_becomes_none(self):
        req = GeneralChatRequest(**_chat(system_prompt="   ", response_style="\t\n"))
        assert req.system_prompt is None
        assert req.response_style is None

    def test_control_chars_are_stripped(self):
        req = GeneralChatRequest(**_chat(system_prompt="se\x00 breve\x07"))
        assert req.system_prompt == "se breve"

    def test_surrounding_whitespace_is_trimmed(self):
        req = GeneralChatRequest(**_chat(response_style="  formal  "))
        assert req.response_style == "formal"

    def test_omitted_prompt_stays_none(self):
        req = GeneralChatRequest(**_chat())
        assert req.system_prompt is None
        assert req.response_style is None

    def test_helper_handles_none(self):
        assert normalize_optional_prompt(None) is None
        assert normalize_optional_prompt("   ") is None
        assert normalize_optional_prompt(" ok ") == "ok"


class TestExtraForbid:
    def test_unknown_field_on_request_is_rejected(self):
        with pytest.raises(ValidationError):
            GeneralChatRequest(**_chat(unexpected="x"))

    def test_unknown_field_on_message_is_rejected(self):
        with pytest.raises(ValidationError):
            Message(role="human", content="hola", extra="x")


class TestAttachedDocumentIdsCeiling:
    def test_fifty_attached_ids_allowed(self):
        req = GeneralChatRequest(**_chat(document_ids=list(range(1, MAX_DOCUMENT_IDS_PER_REQUEST + 1))))
        assert len(req.document_ids) == MAX_DOCUMENT_IDS_PER_REQUEST

    def test_over_ceiling_is_rejected(self):
        with pytest.raises(ValidationError):
            GeneralChatRequest(**_chat(document_ids=list(range(1, MAX_DOCUMENT_IDS_PER_REQUEST + 2))))


class TestGraphTypeValidation:
    def test_blank_entity_type_rejected(self):
        with pytest.raises(ValidationError):
            ExtractEntitiesRelationsRequest(
                content="x",
                document_id=1,
                fragment_id=1,
                allowed_entity_types=["person", "  "],
            )

    def test_valid_extract_request_passes(self):
        req = ExtractEntitiesRelationsRequest(
            content="x",
            document_id=1,
            fragment_id=1,
            allowed_entity_types=["person"],
        )
        assert req.allowed_entity_types == ["person"]

    def test_ontology_blank_relation_type_rejected(self):
        with pytest.raises(ValidationError):
            TranslateGraphQueryRequest(
                question="¿quién?",
                ontology=GraphOntology(entity_types=["person"], relation_types=["   "]),
            )

    def test_valid_translate_request_passes(self):
        req = TranslateGraphQueryRequest(
            question="¿quién?",
            ontology=GraphOntology(entity_types=["person"], relation_types=["works_at"]),
        )
        assert req.ontology.entity_types == ["person"]
