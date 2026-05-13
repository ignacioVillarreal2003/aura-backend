import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
import httpx
from django.conf import settings

from core.authentication.authenticated_user import AuthenticatedUser
from core.authentication.authentication_provider import build_service_user_headers
from core.clients.exceptions import (
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException,
)
from core.clients.http_client import AsyncHttpClient

logger = logging.getLogger(__name__)


@dataclass
class DocumentQuestionResult:
    question: str
    answer: str
    fragments: list[dict[str, Any]] = field(default_factory=list)


class LLMClient:
    def __init__(self):
        self._http_client = AsyncHttpClient(timeout=getattr(settings, "LLM_SERVICE_TIMEOUT", 30))

    async def document_question(
        self,
        messages: list[dict[str, str]],
        user: AuthenticatedUser,
    ) -> DocumentQuestionResult:
        payload = {"messages": messages}

        logger.debug(
            "Calling LLM document-question.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_DOCUMENT_QUESTION_URL,
            },
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

        fragments = self.normalize_fragments(data.get("fragments"))

        return DocumentQuestionResult(
            question=str(data.get("question", "")),
            answer=str(data.get("answer", "")),
            fragments=fragments,
        )

    async def document_question_stream_events(
        self,
        messages: list[dict[str, str]],
        user: AuthenticatedUser,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = {"messages": messages}
        headers = self._build_stream_headers(user)
        url = settings.LLM_DOCUMENT_QUESTION_STREAM_URL

        logger.debug(
            "Calling LLM document-question stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        timeout = httpx.Timeout(
            connect=settings.LLM_STREAM_CONNECT_TIMEOUT,
            read=settings.LLM_STREAM_READ_TIMEOUT,
            write=30.0,
            pool=10.0,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        detail = body.decode("utf-8", errors="replace")[:500]
                        logger.error(
                            "LLM stream HTTP error.",
                            extra={
                                "status_code": response.status_code,
                                "body_preview": detail,
                            },
                        )
                        raise HttpClientException(
                            f"HTTP {response.status_code}",
                            status_code=response.status_code,
                        )

                    async for event in self._iter_sse_json_events(response):
                        yield event

        except httpx.TimeoutException as e:
            raise HttpClientTimeoutException() from e
        except httpx.ConnectError as e:
            raise HttpClientConnectionException() from e
        except HttpClientException:
            raise
        except Exception as e:
            raise HttpClientException(str(e)) from e

    async def _iter_sse_json_events(
        self,
        response: httpx.Response,
    ) -> AsyncIterator[dict[str, Any]]:
        pending_data: str | None = None
        try:
            async for raw_line in response.aiter_lines():
                line = raw_line.rstrip("\r")
                if line.startswith("data:"):
                    pending_data = line[5:].lstrip()
                elif line == "":
                    if pending_data is None:
                        continue
                    try:
                        obj = json.loads(pending_data)
                    except json.JSONDecodeError as e:
                        logger.error(
                            "Invalid SSE JSON from LLM.",
                            extra={"preview": pending_data[:200]},
                        )
                        raise HttpClientException(
                            "Invalid SSE payload from LLM",
                        ) from e
                    if isinstance(obj, dict):
                        yield obj
                    pending_data = None
        finally:
            if pending_data:
                try:
                    obj = json.loads(pending_data)
                except json.JSONDecodeError as e:
                    raise HttpClientException(
                        "Invalid SSE payload from LLM (trailing)",
                    ) from e
                if isinstance(obj, dict):
                    yield obj

    @staticmethod
    def normalize_fragments(raw_fragments: Any) -> list[dict[str, Any]]:
        fragments: list[dict[str, Any]] = []
        if not isinstance(raw_fragments, list):
            return fragments
        for item in raw_fragments:
            if isinstance(item, dict):
                fragments.append(item)
            else:
                fragments.append({"value": item})
        return fragments

    @staticmethod
    def _build_service_headers(user: AuthenticatedUser) -> dict[str, str]:
        headers = build_service_user_headers(user)
        headers["Accept"] = "application/json"
        headers["Content-Type"] = "application/json"
        return headers

    @staticmethod
    def _build_stream_headers(user: AuthenticatedUser) -> dict[str, str]:
        headers = build_service_user_headers(user)
        headers["Accept"] = "text/event-stream"
        headers["Content-Type"] = "application/json"
        return headers


llm_client = LLMClient()
