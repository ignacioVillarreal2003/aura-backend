import logging

from app.application.services.fragment.fragment_query_service.exceptions.fragment_query_service_exception import (
    FragmentQueryInvalidRequestException,
)
from app.application.services.fragment.fragment_query_service.fragment_query_service_settings import (
    FragmentQueryServiceSettings,
)
from app.domain.dtos.fragment.fragment_query_controller.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest,
)
from app.domain.dtos.fragment.fragment_query_controller.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)

logger = logging.getLogger(__name__)


class FragmentQueryServiceValidator:
    def __init__(self, fragment_query_service_settings: FragmentQueryServiceSettings) -> None:
        self._settings = fragment_query_service_settings

    def validate_question_context_fragments_request(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest
    ) -> None:
        self._validate_question(question_context_fragments_request.question)
        self._validate_max_fragments(question_context_fragments_request.max_context_fragments)

    def validate_documents_context_fragments_request(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest
    ) -> None:
        self._validate_document_ids(documents_context_fragments_request.document_ids)

    def _validate_question(self, question: str) -> None:
        if not question or not question.strip():
            raise FragmentQueryInvalidRequestException("Question cannot be empty")

        length = len(question)
        if length < self._settings.min_question_length:
            raise FragmentQueryInvalidRequestException(
                f"Question length ({length}) is below the minimum "
                f"({self._settings.min_question_length})"
            )
        if length > self._settings.max_question_length:
            raise FragmentQueryInvalidRequestException(
                f"Question length ({length}) exceeds the maximum "
                f"({self._settings.max_question_length})"
            )

    def _validate_max_fragments(self, max_fragments: int) -> None:
        if max_fragments < 1:
            raise FragmentQueryInvalidRequestException(
                "max_context_fragments must be at least 1"
            )
        if max_fragments > self._settings.max_fragments:
            raise FragmentQueryInvalidRequestException(
                f"max_context_fragments ({max_fragments}) exceeds the configured limit "
                f"({self._settings.max_fragments})"
            )

    def _validate_document_ids(self, document_ids: list[int]) -> None:
        if not document_ids:
            raise FragmentQueryInvalidRequestException("document_ids cannot be empty")
        if len(document_ids) > self._settings.max_document_ids:
            raise FragmentQueryInvalidRequestException(
                f"document_ids length ({len(document_ids)}) exceeds the configured limit "
                f"({self._settings.max_document_ids})"
            )
        for document_id in document_ids:
            if document_id is None or document_id <= 0:
                raise FragmentQueryInvalidRequestException(
                    f"document_id must be a positive integer, got: {document_id!r}"
                )
        if len(set(document_ids)) != len(document_ids):
            raise FragmentQueryInvalidRequestException(
                "document_ids contains duplicate values"
            )
