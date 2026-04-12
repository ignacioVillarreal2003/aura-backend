import logging
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from core.authentication.authenticated_user import AuthenticatedUser
from core.clients.exceptions import HttpClientException
from core.clients.http_client import AsyncHttpClient

logger = logging.getLogger(__name__)


@dataclass
class DocumentQuestionResult:
    question: str
    answer: str
    fragments: list[dict[str, Any]] = field(default_factory=list)


class LLMClient:
    def __init__(self):
        self._http_client = AsyncHttpClient(timeout=settings.LLM_SERVICE_TIMEOUT)

    async def document_question(
        self,
        messages: list[dict[str, str]],
        user: AuthenticatedUser,
    ) -> DocumentQuestionResult:
        payload = {"messages": messages}

        logger.debug(
            "Calling LLM document-question.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        response = await self._http_client.post(
            url=settings.LLM_DOCUMENT_QUESTION_URL,
            json=payload,
            headers=self._build_service_headers(user),
        )

        try:
            data = response.json()
        except ValueError as e:
            logger.error("LLM returned non-JSON body.")
            raise HttpClientException(
                "Invalid LLM response format",
                status_code=response.status_code,
            ) from e

        raw_fragments = data.get("fragments") or []
        fragments: list[dict[str, Any]] = []
        if isinstance(raw_fragments, list):
            for item in raw_fragments:
                if isinstance(item, dict):
                    fragments.append(item)
                else:
                    fragments.append({"value": item})

        return DocumentQuestionResult(
            question=str(data.get("question", "")),
            answer=str(data.get("answer", "")),
            fragments=fragments,
        )

    @staticmethod
    def _build_service_headers(user: AuthenticatedUser) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Service-Api-Key": settings.SERVICE_API_KEY,
            "X-User-Id": str(user.id),
            "X-User-Email": user.email,
            "X-User-Roles": ",".join(user.roles),
            "X-User-Permissions": ",".join(user.permissions),
        }


llm_client = LLMClient()
