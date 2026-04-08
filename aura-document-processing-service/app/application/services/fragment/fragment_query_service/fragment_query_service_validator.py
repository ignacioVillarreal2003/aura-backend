import logging

from app.application.services.fragment.fragment_query_service.exceptions.fragment_query_service_exception import (
    FragmentQueryInvalidRequestException,
)
from app.application.services.fragment.fragment_query_service.fragment_query_service_settings import (
    FragmentQueryServiceSettings,
)
from app.domain.dtos.fragment.fragment_query.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest,
)
from app.domain.dtos.fragment.fragment_query.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)

logger = logging.getLogger(__name__)


class FragmentQueryServiceValidator:
    def __init__(
            self,
            fragment_query_service_settings: FragmentQueryServiceSettings
    ) -> None:
        self._settings = fragment_query_service_settings

    def validate_question_context_fragments_request(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest
    ) -> None:
        self._validate_question(question_context_fragments_request.question)
        self._validate_max_fragments(question_context_fragments_request.max_fragments)

    def validate_documents_context_fragments_request(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest
    ) -> None:
        self._validate_document_ids(documents_context_fragments_request.document_ids)

    def _validate_question(
            self,
            question: str
    ) -> None:
        if not question or not question.strip():
            raise FragmentQueryInvalidRequestException("The question cannot be empty.")

        length = len(question)
        if length < self._settings.min_question_length:
            raise FragmentQueryInvalidRequestException("The question is shorter than the minimum allowed length.")
        if length > self._settings.max_question_length:
            raise FragmentQueryInvalidRequestException("The question exceeds the maximum allowed length.")

    def _validate_max_fragments(self, max_fragments: int) -> None:
        if max_fragments < 1:
            raise FragmentQueryInvalidRequestException("The maximum number of context fragments must be at least one.")
        if max_fragments > self._settings.max_fragments:
            raise FragmentQueryInvalidRequestException(
                "The maximum number of context fragments exceeds the configured limit."
            )

    def _validate_document_ids(
            self,
            document_ids: list[int]
    ) -> None:
        if not document_ids:
            raise FragmentQueryInvalidRequestException("At least one document identifier is required.")
        if len(document_ids) > self._settings.max_document_ids:
            raise FragmentQueryInvalidRequestException(
                "The number of document identifiers exceeds the configured limit."
            )
        for document_id in document_ids:
            if document_id is None or document_id <= 0:
                raise FragmentQueryInvalidRequestException("Each document identifier must be a positive integer.")
        if len(set(document_ids)) != len(document_ids):
            raise FragmentQueryInvalidRequestException("Document identifiers must not contain duplicates.")
