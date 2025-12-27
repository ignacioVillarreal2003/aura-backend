import logging
from typing import List

from app.application.exceptions.app_exceptions import ValidationError
from app.application.exceptions.context_provider_exception import (
    ContextRetrievalByQuestionError,
    ContextRetrievalByDocumentError
)
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
                                             max_fragments: int = DEFAULT_MAX_FRAGMENTS) -> List[str]:
        try:
            logger.debug(
                "Retrieving fragments by question",
                extra={
                    "question": question,
                    "max_fragments": max_fragments
                }
            )

            self._validate_max_fragments(max_fragments)

            payload = {
                "question": question,
                "max_fragments": max_fragments,
            }

            data = await self._http_client.post(
                url=self._retrieve_fragments_by_question_url,
                json=payload
            )

            if not data:
                logger.warning("Context retrieval by question returned empty response")
                return []

            if not isinstance(data, dict):
                logger.warning(
                    "Context retrieval by question returned non-dict payload",
                    extra={
                        "payload_type": type(data).__name__
                    }
                )
                return []

            fragments = data.get("fragments", [])

            if not isinstance(fragments, list):
                logger.warning(
                    "Invalid fragments format received",
                    extra={
                        "fragments_type": type(fragments).__name__
                    }
                )
                return []

            return fragments

        except Exception as e:
            logger.exception("Failed to retrieve fragments by question")
            raise ContextRetrievalByQuestionError() from e

    def _validate_max_fragments(self,
                                max_fragments: int) -> None:
        if not (self.MIN_MAX_FRAGMENTS <= max_fragments <= self.MAX_MAX_FRAGMENTS):
            logger.warning(
                f"max_fragments must be between {self.MIN_MAX_FRAGMENTS} and {self.MAX_MAX_FRAGMENTS}",
                extra={
                    "max_fragments": max_fragments
                }
            )
            raise ValidationError(
                f"max_fragments must be between {self.MIN_MAX_FRAGMENTS} and {self.MAX_MAX_FRAGMENTS}",
                status_code=500
            )

    async def retrieve_fragments_by_document(self,
                                             document_id: int) -> List[str]:
        try:
            logger.debug(
                "Retrieving fragments by document",
                extra={
                    "document_id": document_id
                }
            )

            payload = {
                "document_id": document_id,
            }

            data = await self._http_client.post(
                url=self._retrieve_fragments_by_document_url,
                json=payload
            )

            if not data:
                logger.warning(
                    "Context retrieval by document returned empty response",
                    extra={
                        "document_id": document_id
                    }
                )
                return []

            if not isinstance(data, dict):
                logger.warning(
                    "Context retrieval by document returned non-dict payload",
                    extra={
                        "payload_type": type(data).__name__
                    }
                )
                return []

            fragments = data.get("fragments", [])

            if not isinstance(fragments, list):
                logger.warning(
                    "Invalid fragments format received",
                    extra={
                        "fragments_type": type(fragments).__name__
                    }
                )
                return []

            return fragments

        except Exception as e:
            logger.exception("Failed to retrieve fragments by document")
            raise ContextRetrievalByDocumentError() from e
