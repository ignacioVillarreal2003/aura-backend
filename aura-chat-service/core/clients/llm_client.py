import asyncio
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


@dataclass
class GeneralChatResult:
    answer: str
    messages: list[dict[str, str]] = field(default_factory=list)


@dataclass
class AgentRunResult:
    answer: str
    messages: list[dict[str, str]] = field(default_factory=list)
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ChecklistGenerateResult:
    title: str
    items: list[dict[str, Any]]
    messages: list[dict[str, str]]
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ReportGenerateResult:
    report_type: str
    content: str
    messages: list[dict[str, str]]
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TimelineGenerateResult:
    title: str
    events: list[dict[str, Any]]
    messages: list[dict[str, str]]
    summary: str = ""
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class QuizGenerateResult:
    title: str
    questions: list[dict[str, Any]]
    messages: list[dict[str, str]]
    instructions: str = ""
    passing_score: int | None = None
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LessonsLearnedGenerateResult:
    title: str
    items: list[dict[str, Any]]
    messages: list[dict[str, str]]
    context: str = ""
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DecisionBriefGenerateResult:
    title: str
    options: list[dict[str, Any]]
    messages: list[dict[str, str]]
    problem: str = ""
    context: str = ""
    risks: str = ""
    recommendation: str = ""
    fragments: list[dict[str, Any]] = field(default_factory=list)


class LLMClient:
    def __init__(self):
        self._http_client = AsyncHttpClient(timeout=getattr(settings, "LLM_SERVICE_TIMEOUT", 30))
        self._stream_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
        )

    async def aclose(self) -> None:
        await self._stream_client.aclose()
        await self._http_client.aclose()

    async def document_question(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> DocumentQuestionResult:
        payload: dict = {"messages": messages}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM document-question.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_DOCUMENT_QUESTION_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_DOCUMENT_QUESTION_URL,
            payload=payload,
            user=user,
            context="document-question",
        )

        return DocumentQuestionResult(
            question=str(data.get("question", "")),
            answer=str(data.get("answer", "")),
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def document_question_stream_events(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"messages": messages}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM document-question stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_DOCUMENT_QUESTION_STREAM_URL,
                payload=payload,
                user=user,
                context="document-question-stream",
        ):
            yield event

    async def general_chat(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            system_prompt: str | None = None,
    ) -> GeneralChatResult:
        payload = self._build_general_chat_payload(messages, system_prompt)

        logger.debug(
            "Calling LLM general-chat.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_GENERAL_CHAT_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_GENERAL_CHAT_URL,
            payload=payload,
            user=user,
            context="general-chat",
        )

        return GeneralChatResult(
            answer=str(data.get("answer", "")),
            messages=data.get("messages") or [],
        )

    async def general_chat_stream_events(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            system_prompt: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._build_general_chat_payload(messages, system_prompt)

        logger.debug(
            "Calling LLM general-chat stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_GENERAL_CHAT_STREAM_URL,
                payload=payload,
                user=user,
                context="general-chat-stream",
        ):
            yield event

    async def rag_agent(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
    ) -> AgentRunResult:
        payload: dict = {"messages": messages}

        logger.debug(
            "Calling LLM rag-agent.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_RAG_AGENT_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_RAG_AGENT_URL,
            payload=payload,
            user=user,
            context="rag-agent",
        )
        return self._build_agent_result(data)

    async def rag_agent_stream_events(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"messages": messages}

        logger.debug(
            "Calling LLM rag-agent stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_RAG_AGENT_STREAM_URL,
                payload=payload,
                user=user,
                context="rag-agent-stream",
        ):
            yield event

    async def agent(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
    ) -> AgentRunResult:
        payload: dict = {"messages": messages}

        logger.debug(
            "Calling LLM agent.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_AGENT_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_AGENT_URL,
            payload=payload,
            user=user,
            context="agent",
        )
        return self._build_agent_result(data)

    async def agent_stream_events(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"messages": messages}

        logger.debug(
            "Calling LLM agent stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_AGENT_STREAM_URL,
                payload=payload,
                user=user,
                context="agent-stream",
        ):
            yield event

    async def generate_checklist(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> ChecklistGenerateResult:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM checklist-generate.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_CHECKLIST_GENERATE_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_CHECKLIST_GENERATE_URL,
            payload=payload,
            user=user,
            context="checklist-generate",
        )

        return ChecklistGenerateResult(
            title=str(data.get("title", "")),
            items=data.get("items") or [],
            messages=data.get("messages") or [],
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def generate_checklist_stream_events(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM checklist-generate stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_CHECKLIST_GENERATE_STREAM_URL,
                payload=payload,
                user=user,
                context="checklist-generate-stream",
        ):
            yield event

    async def generate_report(
            self,
            messages: list[dict[str, str]],
            mode: str,
            report_type: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> ReportGenerateResult:
        payload: dict = {"messages": messages, "mode": mode, "report_type": report_type}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM report-generate.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "report_type": report_type,
                "url": settings.LLM_REPORT_GENERATE_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_REPORT_GENERATE_URL,
            payload=payload,
            user=user,
            context="report-generate",
        )

        return ReportGenerateResult(
            report_type=str(data.get("report_type", report_type)),
            content=str(data.get("content", "")),
            messages=data.get("messages") or [],
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def generate_report_stream_events(
            self,
            messages: list[dict[str, str]],
            mode: str,
            report_type: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"messages": messages, "mode": mode, "report_type": report_type}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM report-generate stream.",
            extra={"user_id": user.id, "message_count": len(messages), "report_type": report_type},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_REPORT_GENERATE_STREAM_URL,
                payload=payload,
                user=user,
                context="report-generate-stream",
        ):
            yield event

    async def generate_timeline(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> TimelineGenerateResult:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM timeline-generate.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_TIMELINE_GENERATE_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_TIMELINE_GENERATE_URL,
            payload=payload,
            user=user,
            context="timeline-generate",
        )

        return TimelineGenerateResult(
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            events=data.get("events") or [],
            messages=data.get("messages") or [],
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def generate_timeline_stream_events(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM timeline-generate stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_TIMELINE_GENERATE_STREAM_URL,
                payload=payload,
                user=user,
                context="timeline-generate-stream",
        ):
            yield event

    async def generate_quiz(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> QuizGenerateResult:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM quiz-generate.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_QUIZ_GENERATE_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_QUIZ_GENERATE_URL,
            payload=payload,
            user=user,
            context="quiz-generate",
        )

        return QuizGenerateResult(
            title=str(data.get("title", "")),
            instructions=str(data.get("instructions", "")),
            passing_score=self._coerce_int(data.get("passing_score")),
            questions=data.get("questions") or [],
            messages=data.get("messages") or [],
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def generate_quiz_stream_events(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM quiz-generate stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_QUIZ_GENERATE_STREAM_URL,
                payload=payload,
                user=user,
                context="quiz-generate-stream",
        ):
            yield event

    async def generate_lessons_learned(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> LessonsLearnedGenerateResult:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM lessons-learned-generate.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_LESSONS_LEARNED_GENERATE_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_LESSONS_LEARNED_GENERATE_URL,
            payload=payload,
            user=user,
            context="lessons-learned-generate",
        )

        return LessonsLearnedGenerateResult(
            title=str(data.get("title", "")),
            context=str(data.get("context", "")),
            items=data.get("items") or [],
            messages=data.get("messages") or [],
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def generate_lessons_learned_stream_events(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM lessons-learned-generate stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_LESSONS_LEARNED_GENERATE_STREAM_URL,
                payload=payload,
                user=user,
                context="lessons-learned-generate-stream",
        ):
            yield event

    async def generate_decision_brief(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> DecisionBriefGenerateResult:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM decision-brief-generate.",
            extra={
                "user_id": user.id,
                "message_count": len(messages),
                "url": settings.LLM_DECISION_BRIEF_GENERATE_URL,
            },
        )

        data = await self._post_json(
            url=settings.LLM_DECISION_BRIEF_GENERATE_URL,
            payload=payload,
            user=user,
            context="decision-brief-generate",
        )

        return DecisionBriefGenerateResult(
            title=str(data.get("title", "")),
            problem=str(data.get("problem", "")),
            context=str(data.get("context", "")),
            risks=str(data.get("risks", "")),
            recommendation=str(data.get("recommendation", "")),
            options=data.get("options") or [],
            messages=data.get("messages") or [],
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def generate_decision_brief_stream_events(
            self,
            messages: list[dict[str, str]],
            mode: str,
            user: AuthenticatedUser,
            chat_id: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"messages": messages, "mode": mode}
        if chat_id is not None:
            payload["chat_id"] = chat_id

        logger.debug(
            "Calling LLM decision-brief-generate stream.",
            extra={"user_id": user.id, "message_count": len(messages)},
        )

        async for event in self._stream_sse_events(
                url=settings.LLM_DECISION_BRIEF_GENERATE_STREAM_URL,
                payload=payload,
                user=user,
                context="decision-brief-generate-stream",
        ):
            yield event

    @staticmethod
    def _require_configured_url(url: str, context: str) -> None:
        if url and url.strip():
            return
        logger.error("LLM endpoint URL is not configured.", extra={"context": context})
        raise HttpClientException(
            f"LLM service endpoint not configured ({context})",
            status_code=503,
        )

    async def _post_json(
            self,
            url: str,
            payload: dict,
            user: AuthenticatedUser,
            context: str,
    ) -> dict[str, Any]:
        self._require_configured_url(url, context)
        response = await self._http_client.post(
            url=url,
            json=payload,
            headers=self._build_service_headers(user),
        )

        try:
            data = response.json()
        except ValueError as e:
            logger.error("LLM %s returned non-JSON body.", context, exc_info=True)
            raise HttpClientException(
                "Invalid LLM response format",
                status_code=response.status_code,
            ) from e

        if not isinstance(data, dict):
            logger.error("LLM %s returned a non-object JSON body.", context, exc_info=True)
            raise HttpClientException(
                "Invalid LLM response format",
                status_code=response.status_code,
            )
        return data

    _STREAM_RETRYABLE = frozenset({429, 502, 503, 504})

    async def _stream_sse_events(
            self,
            url: str,
            payload: dict,
            user: AuthenticatedUser,
            context: str = "stream",
    ) -> AsyncIterator[dict[str, Any]]:
        self._require_configured_url(url, context)
        headers = self._build_stream_headers(user)
        timeout = httpx.Timeout(
            connect=getattr(settings, "LLM_STREAM_CONNECT_TIMEOUT", 10.0),
            read=getattr(settings, "LLM_STREAM_READ_TIMEOUT", 120.0),
            write=30.0,
            pool=10.0,
        )
        max_attempts = 2

        for attempt in range(max_attempts):
            try:
                async with self._stream_client.stream(
                        "POST",
                        url,
                        json=payload,
                        headers=headers,
                        timeout=timeout,
                ) as response:
                    if response.status_code in self._STREAM_RETRYABLE and attempt < max_attempts - 1:
                        delay = 0.5 * (2 ** attempt)
                        logger.warning(
                            "Retryable LLM stream error, will retry.",
                            extra={
                                "status_code": response.status_code,
                                "url": url,
                                "attempt": attempt + 1,
                                "delay_seconds": delay,
                            },
                        )
                        await asyncio.sleep(delay)
                        continue

                    if response.status_code >= 400:
                        body = await response.aread()
                        detail = body.decode("utf-8", errors="replace")[:500]
                        logger.error(
                            "LLM stream HTTP error.",
                            extra={
                                "status_code": response.status_code,
                                "url": url,
                                "body_preview": detail,
                            },
                        )
                        raise HttpClientException(
                            f"HTTP {response.status_code}",
                            status_code=response.status_code,
                        )

                    async for event in self._iter_sse_json_events(response):
                        yield event
                    return

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
        async for raw_line in response.aiter_lines():
            line = raw_line.rstrip("\r")
            if line.startswith("data:"):
                chunk = line[5:].lstrip()
                pending_data = (pending_data + "\n" + chunk) if pending_data is not None else chunk
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
        if pending_data is not None:
            try:
                obj = json.loads(pending_data)
            except json.JSONDecodeError as e:
                raise HttpClientException(
                    "Invalid SSE payload from LLM (trailing)",
                ) from e
            if isinstance(obj, dict):
                yield obj

    @staticmethod
    def _build_general_chat_payload(
            messages: list[dict[str, str]],
            system_prompt: str | None,
    ) -> dict:
        payload: dict = {"messages": messages}
        if system_prompt is not None:
            stripped = system_prompt.strip()
            if stripped:
                payload["system_prompt"] = stripped
        return payload

    def _build_agent_result(self, data: dict[str, Any]) -> AgentRunResult:
        out_messages = data.get("messages") or []
        return AgentRunResult(
            answer=self._last_assistant_content(out_messages),
            messages=out_messages,
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    @staticmethod
    def _last_assistant_content(messages: Any) -> str:
        if not isinstance(messages, list):
            return ""
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "assistant":
                return str(message.get("content", ""))
        return ""

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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
