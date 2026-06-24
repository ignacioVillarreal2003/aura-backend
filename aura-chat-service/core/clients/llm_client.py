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
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LessonsLearnedGenerateResult:
    title: str
    items: list[dict[str, Any]]
    messages: list[dict[str, str]]
    description: str = ""
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DocumentSummaryResult:
    summary: str
    title: str = ""
    description: str = ""
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DocumentActionResult:
    result: str
    instruction: str
    title: str = ""
    description: str = ""
    action: str | None = None
    fragments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DecisionBriefGenerateResult:
    title: str
    options: list[dict[str, Any]]
    messages: list[dict[str, str]]
    description: str = ""
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

    @staticmethod
    def _apply_overrides(
            payload: dict,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> dict:
        for key, value in (("system_prompt", system_prompt), ("response_style", response_style)):
            if value:
                stripped = value.strip()
                if stripped:
                    payload[key] = stripped
        for key, flag in (("retrieve_context", retrieve_context), ("process_documents", process_documents)):
            if flag is not None:
                payload[key] = bool(flag)
        if document_ids is not None:
            payload["document_ids"] = list(document_ids)
        return payload

    async def _generate(
            self,
            *,
            url: str,
            context: str,
            payload: dict,
            user: AuthenticatedUser,
            log_extra: dict[str, Any],
    ) -> dict[str, Any]:
        logger.debug(
            "Calling LLM %s.",
            context,
            extra={"user_id": user.id, "url": url, **log_extra},
        )
        return await self._post_json(url=url, payload=payload, user=user, context=context)

    async def _generate_stream(
            self,
            *,
            url: str,
            context: str,
            payload: dict,
            user: AuthenticatedUser,
            log_extra: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        logger.debug(
            "Calling LLM %s.",
            context,
            extra={"user_id": user.id, **log_extra},
        )
        async for event in self._stream_sse_events(
                url=url, payload=payload, user=user, context=context,
        ):
            yield event

    async def document_question(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> DocumentQuestionResult:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents,
        )
        data = await self._generate(
            url=settings.LLM_DOCUMENT_QUESTION_URL,
            context="document-question",
            payload=payload,
            user=user,
            log_extra={"message_count": len(messages)},
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
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents,
        )
        async for event in self._generate_stream(
                url=settings.LLM_DOCUMENT_QUESTION_STREAM_URL,
                context="document-question-stream",
                payload=payload,
                user=user,
                log_extra={"message_count": len(messages)},
        ):
            yield event

    async def general_chat(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> GeneralChatResult:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents,
        )
        data = await self._generate(
            url=settings.LLM_GENERAL_CHAT_URL,
            context="general-chat",
            payload=payload,
            user=user,
            log_extra={"message_count": len(messages)},
        )
        return GeneralChatResult(
            answer=str(data.get("answer", "")),
            messages=data.get("messages") or [],
        )

    async def general_chat_stream_events(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents,
        )
        async for event in self._generate_stream(
                url=settings.LLM_GENERAL_CHAT_STREAM_URL,
                context="general-chat-stream",
                payload=payload,
                user=user,
                log_extra={"message_count": len(messages)},
        ):
            yield event

    async def rag_agent(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> AgentRunResult:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents,
        )
        data = await self._generate(
            url=settings.LLM_RAG_AGENT_URL,
            context="rag-agent",
            payload=payload,
            user=user,
            log_extra={"message_count": len(messages)},
        )
        return self._build_agent_result(data)

    async def rag_agent_stream_events(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents,
        )
        async for event in self._generate_stream(
                url=settings.LLM_RAG_AGENT_STREAM_URL,
                context="rag-agent-stream",
                payload=payload,
                user=user,
                log_extra={"message_count": len(messages)},
        ):
            yield event

    async def generate_checklist(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> ChecklistGenerateResult:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        data = await self._generate(
            url=settings.LLM_CHECKLIST_GENERATE_URL,
            context="checklist-generate",
            payload=payload,
            user=user,
            log_extra={"message_count": len(messages)},
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
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        async for event in self._generate_stream(
                url=settings.LLM_CHECKLIST_GENERATE_STREAM_URL,
                context="checklist-generate-stream",
                payload=payload,
                user=user,
                log_extra={"message_count": len(messages)},
        ):
            yield event

    async def generate_report(
            self,
            messages: list[dict[str, str]],
            report_type: str,
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> ReportGenerateResult:
        payload = self._apply_overrides(
            {"messages": messages, "report_type": report_type, "chat_id": chat_id},
            system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        data = await self._generate(
            url=settings.LLM_REPORT_GENERATE_URL,
            context="report-generate",
            payload=payload,
            user=user,
            log_extra={"message_count": len(messages), "report_type": report_type},
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
            report_type: str,
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"messages": messages, "report_type": report_type, "chat_id": chat_id},
            system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        async for event in self._generate_stream(
                url=settings.LLM_REPORT_GENERATE_STREAM_URL,
                context="report-generate-stream",
                payload=payload,
                user=user,
                log_extra={"message_count": len(messages), "report_type": report_type},
        ):
            yield event

    async def generate_timeline(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> TimelineGenerateResult:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        data = await self._generate(
            url=settings.LLM_TIMELINE_GENERATE_URL,
            context="timeline-generate",
            payload=payload,
            user=user,
            log_extra={"message_count": len(messages)},
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
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        async for event in self._generate_stream(
                url=settings.LLM_TIMELINE_GENERATE_STREAM_URL,
                context="timeline-generate-stream",
                payload=payload,
                user=user,
                log_extra={"message_count": len(messages)},
        ):
            yield event

    async def generate_quiz(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> QuizGenerateResult:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        data = await self._generate(
            url=settings.LLM_QUIZ_GENERATE_URL,
            context="quiz-generate",
            payload=payload,
            user=user,
            log_extra={"message_count": len(messages)},
        )
        return QuizGenerateResult(
            title=str(data.get("title", "")),
            instructions=str(data.get("instructions", "")),
            questions=data.get("questions") or [],
            messages=data.get("messages") or [],
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def generate_quiz_stream_events(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        async for event in self._generate_stream(
                url=settings.LLM_QUIZ_GENERATE_STREAM_URL,
                context="quiz-generate-stream",
                payload=payload,
                user=user,
                log_extra={"message_count": len(messages)},
        ):
            yield event

    async def generate_lessons_learned(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> LessonsLearnedGenerateResult:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        data = await self._generate(
            url=settings.LLM_LESSONS_LEARNED_GENERATE_URL,
            context="lessons-learned-generate",
            payload=payload,
            user=user,
            log_extra={"message_count": len(messages)},
        )
        return LessonsLearnedGenerateResult(
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            items=data.get("items") or [],
            messages=data.get("messages") or [],
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def generate_lessons_learned_stream_events(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        async for event in self._generate_stream(
                url=settings.LLM_LESSONS_LEARNED_GENERATE_STREAM_URL,
                context="lessons-learned-generate-stream",
                payload=payload,
                user=user,
                log_extra={"message_count": len(messages)},
        ):
            yield event

    async def generate_decision_brief(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> DecisionBriefGenerateResult:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        data = await self._generate(
            url=settings.LLM_DECISION_BRIEF_GENERATE_URL,
            context="decision-brief-generate",
            payload=payload,
            user=user,
            log_extra={"message_count": len(messages)},
        )
        return DecisionBriefGenerateResult(
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            context=str(data.get("context", "")),
            risks=str(data.get("risks", "")),
            recommendation=str(data.get("recommendation", "")),
            options=data.get("options") or [],
            messages=data.get("messages") or [],
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def execute_document_summary(
            self,
            document_ids: list[int],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> DocumentSummaryResult:
        payload = self._apply_overrides(
            {"document_ids": document_ids, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents,
        )
        data = await self._generate(
            url=settings.LLM_DOCUMENT_SUMMARY_URL,
            context="document-summary",
            payload=payload,
            user=user,
            log_extra={"document_count": len(document_ids)},
        )
        return DocumentSummaryResult(
            summary=str(data.get("summary", "")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def execute_document_summary_stream_events(
            self,
            document_ids: list[int],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"document_ids": document_ids, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents,
        )
        async for event in self._generate_stream(
                url=settings.LLM_DOCUMENT_SUMMARY_STREAM_URL,
                context="document-summary-stream",
                payload=payload,
                user=user,
                log_extra={"document_count": len(document_ids)},
        ):
            yield event

    async def execute_document_action(
            self,
            document_ids: list[int],
            instruction: str,
            action: str | None,
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> DocumentActionResult:
        payload: dict = {"document_ids": document_ids, "instruction": instruction, "chat_id": chat_id}
        if action is not None:
            payload["action"] = action
        self._apply_overrides(payload, system_prompt, response_style, retrieve_context, process_documents)
        data = await self._generate(
            url=settings.LLM_DOCUMENT_ACTION_URL,
            context="document-action",
            payload=payload,
            user=user,
            log_extra={"document_count": len(document_ids)},
        )
        return DocumentActionResult(
            result=str(data.get("result", "")),
            instruction=str(data.get("instruction", instruction)),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            action=data.get("action"),
            fragments=self.normalize_fragments(data.get("fragments")),
        )

    async def execute_document_action_stream_events(
            self,
            document_ids: list[int],
            instruction: str,
            action: str | None,
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload: dict = {"document_ids": document_ids, "instruction": instruction, "chat_id": chat_id}
        if action is not None:
            payload["action"] = action
        self._apply_overrides(payload, system_prompt, response_style, retrieve_context, process_documents)
        async for event in self._generate_stream(
                url=settings.LLM_DOCUMENT_ACTION_STREAM_URL,
                context="document-action-stream",
                payload=payload,
                user=user,
                log_extra={"document_count": len(document_ids)},
        ):
            yield event

    async def generate_decision_brief_stream_events(
            self,
            messages: list[dict[str, str]],
            user: AuthenticatedUser,
            chat_id: int,
            system_prompt: str | None = None,
            response_style: str | None = None,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = self._apply_overrides(
            {"messages": messages, "chat_id": chat_id}, system_prompt, response_style,
            retrieve_context, process_documents, document_ids,
        )
        async for event in self._generate_stream(
                url=settings.LLM_DECISION_BRIEF_GENERATE_STREAM_URL,
                context="decision-brief-generate-stream",
                payload=payload,
                user=user,
                log_extra={"message_count": len(messages)},
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
    async def evaluate_feedback(
            self,
            user_query: str,
            assistant_response: str,
            chat_history: list[dict[str, str]],
            user: AuthenticatedUser,
            fragments: list[dict[str, Any]] | None = None,
            feedback_reason: str | None = None,
            feedback_comment: str | None = None,
            mode: str = "direct",
    ) -> dict[str, Any]:
        payload = {
            "user_query": user_query,
            "assistant_response": assistant_response,
            "chat_history": chat_history,
            "fragments": fragments,
            "feedback_reason": feedback_reason,
            "feedback_comment": feedback_comment,
            "mode": mode,
        }
        return await self._generate(
            url=settings.LLM_FEEDBACK_EVALUATION_URL,
            context="feedback-evaluate",
            payload=payload,
            user=user,
            log_extra={"feedback_reason": feedback_reason},
        )

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
