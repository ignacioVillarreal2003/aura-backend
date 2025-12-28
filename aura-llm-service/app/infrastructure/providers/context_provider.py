import logging
from typing import Any, List, Optional, Sequence

from app.application.exceptions.app_exceptions import ValidationError
from app.infrastructure.providers.exceptions.context_provider_exception import (
    ContextRetrievalByQuestionError,
    ContextRetrievalByDocumentError
)
from app.infrastructure.http_client.exceptions.http_client_exceptions import HttpClientError
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface
from app.infrastructure.providers.interfaces.context_provider_interface import ContextProviderInterface

logger = logging.getLogger(__name__)


class ContextProvider(ContextProviderInterface):
    DEFAULT_MAX_FRAGMENTS: int = 3
    MIN_MAX_FRAGMENTS: int = 1
    MAX_MAX_FRAGMENTS: int = 6

    def __init__(self,
                 http_client: HttpClientInterface,
                 retrieve_fragments_by_question_url: str,
                 retrieve_fragments_by_document_url: str) -> None:
        self._http_client = http_client
        self._retrieve_fragments_by_question_url = retrieve_fragments_by_question_url
        self._retrieve_fragments_by_document_url = retrieve_fragments_by_document_url

    async def retrieve_fragments_by_question(self,
                                             question: str,
                                             max_fragments: Optional[int] = None) -> Sequence[str]:
        self._validate_question(question)
        max_fragments = self._normalize_max_fragments(max_fragments)

        logger.debug(
            "Retrieving fragments by question",
            extra={
                "question": question,
                "max_fragments": max_fragments
            }
        )

        payload = {
            "question": question,
            "max_fragments": max_fragments
        }

        try:
            data = await self._http_client.post(
                url=self._retrieve_fragments_by_question_url,
                json=payload
            )
            return self._extract_and_validate_fragments(
                data=data,
                max_fragments=max_fragments,
                error_class=ContextRetrievalByQuestionError,
                operation="question retrieval"
            )
        except HttpClientError as e:
            logger.exception("HTTP client error while retrieving fragments by question")
            raise ContextRetrievalByQuestionError("Upstream HTTP error") from e

    async def retrieve_fragments_by_document(self,
                                             document_id: int) -> Sequence[str]:
        self._validate_document_id(document_id)

        logger.debug(
            "Retrieving fragments by document",
            extra={
                "document_id": document_id
            }
        )

        payload = {
            "document_id": document_id
        }

        try:
            data = await self._http_client.post(
                url=self._retrieve_fragments_by_document_url,
                json=payload
            )
            return self._extract_and_validate_fragments(
                data=data,
                max_fragments=None,
                error_class=ContextRetrievalByDocumentError,
                operation="document retrieval"
            )
        except HttpClientError as e:
            logger.exception("HTTP client error while retrieving fragments by document")
            raise ContextRetrievalByDocumentError("Upstream HTTP error") from e

    @staticmethod
    def _validate_question(question: str) -> None:
        if not question or not question.strip():
            logger.warning("Empty question provided")
            raise ValidationError(
                "Question cannot be empty",
                status_code=400
            )

    @staticmethod
    def _validate_document_id(document_id: int) -> None:
        if document_id <= 0:
            logger.warning(
                "Invalid document_id provided",
                extra={"document_id": document_id}
            )
            raise ValidationError(
                "document_id must be a positive integer",
                status_code=400
            )

    def _validate_max_fragments(self,
                                max_fragments: int) -> None:
        if not (self.MIN_MAX_FRAGMENTS <= max_fragments <= self.MAX_MAX_FRAGMENTS):
            logger.warning(
                f"max_fragments out of range [{self.MIN_MAX_FRAGMENTS}, {self.MAX_MAX_FRAGMENTS}]",
                extra={"max_fragments": max_fragments}
            )
            raise ValidationError(
                f"max_fragments must be between {self.MIN_MAX_FRAGMENTS} and {self.MAX_MAX_FRAGMENTS}",
                status_code=400
            )

    def _normalize_max_fragments(self,
                                 max_fragments: Optional[int]) -> int:
        if max_fragments is None:
            return self.DEFAULT_MAX_FRAGMENTS

        self._validate_max_fragments(max_fragments)
        return max_fragments

    def _extract_and_validate_fragments(self,
                                        data: Any,
                                        max_fragments: Optional[int],
                                        error_class: type,
                                        operation: str) -> List[str]:
        self._validate_response_structure(data, error_class, operation)

        fragments = data.get("fragments", [])
        self._validate_fragments_type(fragments, error_class, operation)

        return self._filter_valid_fragments(fragments, max_fragments)

    @staticmethod
    def _validate_response_structure(data: Any,
                                     error_class: type,
                                     operation: str) -> None:
        if not isinstance(data, dict):
            logger.error(
                f"{operation} returned non-dict payload",
                extra={
                    "type": type(data).__name__
                }
            )
            raise error_class("Invalid payload structure from context service")

    @staticmethod
    def _validate_fragments_type(fragments: Any,
                                 error_class: type,
                                 operation: str) -> None:
        if not isinstance(fragments, list):
            logger.error(
                f"{operation} returned invalid fragments format",
                extra={
                    "fragments_type": type(fragments).__name__
                }
            )
            raise error_class("Invalid fragments format from context service")

    @staticmethod
    def _filter_valid_fragments(fragments: List[Any],
                                max_fragments: Optional[int]) -> List[str]:
        validated_fragments: List[str] = []

        for item in fragments:
            if not isinstance(item, str):
                logger.warning(
                    "Skipping non-string fragment",
                    extra={
                        "item_type": type(item).__name__
                    }
                )
                continue

            validated_fragments.append(item)

            if max_fragments is not None and len(validated_fragments) >= max_fragments:
                break

        return validated_fragments
