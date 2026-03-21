import logging

from app.application.services.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings
)
from app.application.services.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryInvalidRequestException
)
from app.domain.dtos.document_query_controller.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_query_controller.question_context_fragments_request import QuestionContextFragmentsRequest

logger = logging.getLogger(__name__)


class DocumentQueryServiceRequestValidator:
    def __init__(self, document_query_service_settings: DocumentQueryServiceSettings) -> None:
        self._settings = document_query_service_settings

    def validate_question_context_fragments_request(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest
    ) -> None:
        self._validate_question(question_context_fragments_request.question)
        self._validate_max_fragments(question_context_fragments_request.max_context_fragments)

    def validate_document_context_fragments_request(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest
    ) -> None:
        self._validate_document_id(document_context_fragments_request.document_id)

    def validate_pagination(self, page: int | None, size: int | None) -> None:
        if page is not None and page < 1:
            raise DocumentQueryInvalidRequestException(
                f"page must be a positive integer, got {page}"
            )
        if size is not None:
            if size < 1:
                raise DocumentQueryInvalidRequestException(
                    f"size must be a positive integer, got {size}"
                )
            if size > self._settings.max_page_size:
                raise DocumentQueryInvalidRequestException(
                    f"size ({size}) exceeds the maximum allowed page size "
                    f"({self._settings.max_page_size})"
                )

    def _validate_question(self, question: str) -> None:
        if not question or not question.strip():
            raise DocumentQueryInvalidRequestException("Question cannot be empty")

        length = len(question)

        if length < self._settings.min_question_length:
            raise DocumentQueryInvalidRequestException(
                f"Question length ({length}) is below the minimum "
                f"({self._settings.min_question_length})"
            )

        if length > self._settings.max_question_length:
            raise DocumentQueryInvalidRequestException(
                f"Question length ({length}) exceeds the maximum "
                f"({self._settings.max_question_length})"
            )

    def _validate_max_fragments(self, max_fragments: int) -> None:
        if max_fragments < 1:
            raise DocumentQueryInvalidRequestException(
                "max_context_fragments must be at least 1"
            )

        if max_fragments > self._settings.max_fragments:
            raise DocumentQueryInvalidRequestException(
                f"max_context_fragments ({max_fragments}) exceeds the configured limit "
                f"({self._settings.max_fragments})"
            )

    def _validate_document_id(self, document_id: int) -> None:
        if document_id is None or document_id <= 0:
            raise DocumentQueryInvalidRequestException(
                f"document_id must be a positive integer, got: {document_id!r}"
            )
