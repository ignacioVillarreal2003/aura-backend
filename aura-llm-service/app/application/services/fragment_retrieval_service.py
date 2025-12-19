import logging
from typing import List

from app.application.exceptions.fragment_retrieval_service_exception import FragmentRetrievalServiceError
from app.infrastructure.http.http_client import HttpClient

logger = logging.getLogger(__name__)


class FragmentRetrievalService:
    def __init__(self,
                 http_client: HttpClient,
                 fragment_retrieval_url: str) -> None:
        self._http_client = http_client
        self._fragment_retrieval_url = fragment_retrieval_url

    async def get_fragments(self,
                            question: str,
                            max_fragments: int) -> List[str]:
        logger.debug("Retrieving RAG fragments")

        payload = {
            "question": question,
            "max_fragments": max_fragments,
        }

        try:
            data = await self._http_client.post(
                self._fragment_retrieval_url,
                json=payload
            )

            if not data:
                logger.warning("RAG retrieval returned empty response")
                return []

            fragments = data.get("fragments", [])

            if not isinstance(fragments, list):
                logger.warning("Invalid fragments format received")
                return []

            return fragments

        except Exception as e:
            logger.error("Failed to retrieve RAG fragments")
            raise FragmentRetrievalServiceError("Error retrieving fragments") from e
