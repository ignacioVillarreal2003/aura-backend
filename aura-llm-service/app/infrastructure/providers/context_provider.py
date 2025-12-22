import logging
from typing import List

from app.application.exceptions.context_provider_exception import (
    ContextRetrievalByQuestionError,
    ContextRetrievalByDocumentError,
)
from app.infrastructure.http_client.http_client import HttpClient

logger = logging.getLogger(__name__)


class ContextProvider:
    DEFAULT_MAX_FRAGMENTS = 3

    def __init__(self,
                 http_client: HttpClient,
                 retrieve_fragments_by_question_url: str,
                 retrieve_fragments_by_document_url: str) -> None:
        self._http_client = http_client
        self._retrieve_fragments_by_question_url = retrieve_fragments_by_question_url
        self._retrieve_fragments_by_document_url = retrieve_fragments_by_document_url

    async def retrieve_fragments_by_question(self,
                                             question: str,
                                             max_fragments: int = 3) -> List[str]:
        if max_fragments < 1:
            logger.warning(
                "max_fragments must be greater than 0",
                extra={
                    "max_fragments": max_fragments
                }
            )
            max_fragments = self.DEFAULT_MAX_FRAGMENTS

        logger.debug(
            "Retrieving fragments by question",
            extra={
                "question": question,
                "max_fragments": max_fragments
            }
        )

        payload = {
            "question": question,
            "max_fragments": max_fragments,
        }

        try:
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

    async def retrieve_fragments_by_document(self,
                                             document_id: int) -> List[str]:
        logger.debug(
            "Retrieving fragments by document",
            extra={
                "document_id": document_id
            }
        )

        payload = {
            "document_id": document_id,
        }

        try:
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
