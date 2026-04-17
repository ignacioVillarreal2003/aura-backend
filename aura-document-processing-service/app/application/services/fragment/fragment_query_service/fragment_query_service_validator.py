from typing import Optional

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
        self._validate_question_max_fragments(
            question_context_fragments_request.question_max_fragments
        )
        if question_context_fragments_request.use_keywords is True:
            self._validate_keywords_max_fragments(
                question_context_fragments_request.keywords_max_fragments
            )
        self._validate_rerank_fields(question_context_fragments_request)

    def validate_documents_context_fragments_request(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest
    ) -> None:
        self._validate_document_ids(documents_context_fragments_request.document_ids)

    def _validate_rerank_fields(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest
    ) -> None:
        if question_context_fragments_request.use_rerank is not True:
            if question_context_fragments_request.rerank_max_fragments is not None:
                raise FragmentQueryInvalidRequestException(
                    "rerank_max_fragments may only be set when use_rerank is true."
                )
            return

        if not self._settings.rerank_enabled:
            raise FragmentQueryInvalidRequestException("Reranking is disabled on this service.")

    def _validate_question_max_fragments(self, question_max_fragments: int) -> None:
        if question_max_fragments < 1:
            raise FragmentQueryInvalidRequestException(
                "The maximum number of context fragments for the question must be at least one."
            )
        if question_max_fragments > self._settings.max_fragments:
            raise FragmentQueryInvalidRequestException(
                "The maximum number of context fragments for the question exceeds the configured limit."
            )

    def _validate_keywords_max_fragments(self, keywords_max_fragments: Optional[int]) -> None:
        if keywords_max_fragments is None:
            return
        if keywords_max_fragments < 1:
            raise FragmentQueryInvalidRequestException(
                "The maximum number of context fragments for keywords must be at least one."
            )
        if keywords_max_fragments > self._settings.max_fragments:
            raise FragmentQueryInvalidRequestException(
                "The maximum number of context fragments for keywords exceeds the configured limit."
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
