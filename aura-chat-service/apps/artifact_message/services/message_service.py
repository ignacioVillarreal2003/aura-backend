import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact_message.exceptions import (
    ChatLockedException,
    LLMServiceException,
    MessageAccessDeniedException,
    MessageDeleteForbiddenException,
    MessageNotFoundException,
    ReaderCannotSendMessageException,
)
from apps.artifact_message.models import ArtifactMessage
from apps.artifact_message.repositories.message_repository import message_repository
from apps.artifact_message.serializers import MessageResponse
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization.permissions import (
    DELETE_MESSAGE,
    LIST_MESSAGES,
    MANAGE_MESSAGES,
    SEND_MESSAGE,
)
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import (
    AgentRunResult,
    DocumentQuestionResult,
    GeneralChatResult,
    llm_client,
)

logger = logging.getLogger(__name__)


class ChatAIMode:
    DOCUMENT_QUESTION = "document_question"
    GENERAL_CHAT = "general_chat"
    RAG_AGENT = "rag_agent"
    AGENT = "agent"

    DEFAULT = DOCUMENT_QUESTION
    ALL = frozenset({DOCUMENT_QUESTION, GENERAL_CHAT, RAG_AGENT, AGENT})

    @classmethod
    def normalize(cls, value: Any) -> str:
        if isinstance(value, str) and value in cls.ALL:
            return value
        return cls.DEFAULT


def _broadcast_user_message_to_chat_group(chat_id: int, msg: ArtifactMessage) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    payload = MessageResponse(msg).data
    try:
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {"type": "user_message", **payload},
        )
    except Exception:
        logger.warning(
            "Failed to broadcast user_message for chat %d", chat_id, exc_info=True
        )


def broadcast_chat_ai_lock_change(chat_id: int, locked: bool) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {"type": "chat_ai_lock_changed", "locked": locked},
        )
    except Exception:
        logger.warning(
            "Failed to broadcast ai_lock_change for chat %d", chat_id, exc_info=True
        )


@dataclass
class DocumentQuestionRunResult:
    question: str
    answer: str
    fragments: list[dict[str, Any]]
    assistant_message: ArtifactMessage | None = None


class MessageService:
    def send_message(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            text: str,
    ) -> ArtifactMessage:
        AccessControl.require_permissions(user, frozenset({SEND_MESSAGE}))
        self._require_send_access(chat_id, user.id)

        with transaction.atomic():
            msg = message_repository.create(
                chat_id=chat_id,
                message=text,
                sender_type=ArtifactMessage.SenderType.USER,
                created_by=user.id,
            )
            chat_repository.touch_last_message_at(chat_id, updated_by=user.id)
            membership_repository.mark_as_read(chat_id, user.id)

        logger.info(
            "User message saved.",
            extra={"chat_id": chat_id, "message_id": msg.id, "user_id": user.id},
        )
        _broadcast_user_message_to_chat_group(chat_id, msg)
        return msg

    def _save_ai_message(
            self,
            chat_id: int,
            user_id: int,
            answer: str,
            fragments: list | None = None,
    ) -> ArtifactMessage:
        with transaction.atomic():
            msg = message_repository.create(
                chat_id=chat_id,
                message=answer,
                sender_type=ArtifactMessage.SenderType.ASSISTANT,
                created_by=user_id,
                fragments=fragments or None,
            )
            chat_repository.touch_last_message_at(chat_id, updated_by=user_id)
        return msg

    def get_messages(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({LIST_MESSAGES}))
        self._require_access(chat_id, user.id)
        return message_repository.get_messages_by_chat(chat_id, user_id=user.id)

    def get_messages_admin(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({MANAGE_MESSAGES}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        return message_repository.get_messages_by_chat(chat_id, user_id=user.id)

    @staticmethod
    async def _build_llm_messages(chat_id: int) -> list[dict[str, str]]:
        limit = getattr(settings, "LLM_CONTEXT_MESSAGE_LIMIT", 10)
        recent = await sync_to_async(message_repository.get_recent_messages)(
            chat_id, limit=limit
        )
        ordered = list(reversed(recent))
        # In a shared chat several people speak as "human". Tag each human turn
        # with its author so the model can tell participants apart; keep
        # single-user chats clean (no tagging) to avoid polluting the prompt.
        human_senders = {
            m.created_by
            for m in ordered
            if m.sender_type == ArtifactMessage.SenderType.USER
        }
        multi_user = len(human_senders) > 1
        messages: list[dict[str, str]] = []
        for m in ordered:
            if m.sender_type == ArtifactMessage.SenderType.USER:
                content = m.message
                if multi_user and m.created_by is not None:
                    content = f"[User {m.created_by}] {content}"
                messages.append({"role": "human", "content": content})
            elif m.sender_type == ArtifactMessage.SenderType.ASSISTANT:
                messages.append({"role": "assistant", "content": m.message})
        return messages

    async def run_document_question(
            self,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> DocumentQuestionRunResult:
        messages = await self._build_llm_messages(chat_id)
        system_prompt, response_style = await self._get_chat_prompt_style(chat_id)

        try:
            llm_out: DocumentQuestionResult = await llm_client.document_question(
                messages, user, chat_id=chat_id,
                system_prompt=system_prompt, response_style=response_style,
            )
        except HttpClientException as e:
            logger.error(
                "LLM document-question failed: %s",
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_url": getattr(settings, "LLM_DOCUMENT_QUESTION_URL", ""),
                },
                exc_info=True,
            )
            raise LLMServiceException() from e

        assistant_msg: ArtifactMessage | None = None
        if llm_out.answer.strip():
            assistant_msg = await sync_to_async(self._save_ai_message)(
                chat_id, user.id, llm_out.answer, llm_out.fragments or None
            )
            logger.info(
                "AI response saved.",
                extra={"chat_id": chat_id, "message_id": assistant_msg.id},
            )

        return DocumentQuestionRunResult(
            question=llm_out.question,
            answer=llm_out.answer,
            fragments=llm_out.fragments,
            assistant_message=assistant_msg,
        )

    async def run_ai_reply(
            self,
            mode: str,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> DocumentQuestionRunResult:
        if mode == ChatAIMode.GENERAL_CHAT:
            return await self.run_general_chat(user, chat_id)
        if mode == ChatAIMode.RAG_AGENT:
            return await self.run_rag_agent(user, chat_id)
        if mode == ChatAIMode.AGENT:
            return await self.run_agent(user, chat_id)
        return await self.run_document_question(user, chat_id)

    async def run_general_chat(
            self,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> DocumentQuestionRunResult:
        messages = await self._build_llm_messages(chat_id)
        system_prompt, response_style = await self._get_chat_prompt_style(chat_id)
        try:
            result: GeneralChatResult = await llm_client.general_chat(
                messages, user, chat_id=chat_id,
                system_prompt=system_prompt, response_style=response_style,
            )
        except HttpClientException as e:
            logger.error(
                "LLM general-chat failed: %s",
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_url": getattr(settings, "LLM_GENERAL_CHAT_URL", ""),
                },
                exc_info=True,
            )
            raise LLMServiceException() from e

        assistant_msg = await self._persist_ai_answer(chat_id, user.id, result.answer, None)
        return DocumentQuestionRunResult(
            question="",
            answer=result.answer,
            fragments=[],
            assistant_message=assistant_msg,
        )

    async def run_rag_agent(
            self,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> DocumentQuestionRunResult:
        return await self._run_agent_flow(
            user=user,
            chat_id=chat_id,
            caller=llm_client.rag_agent,
            url_setting_name="LLM_RAG_AGENT_URL",
            label="rag-agent",
        )

    async def run_agent(
            self,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> DocumentQuestionRunResult:
        return await self._run_agent_flow(
            user=user,
            chat_id=chat_id,
            caller=llm_client.agent,
            url_setting_name="LLM_AGENT_URL",
            label="agent",
        )

    async def _run_agent_flow(
            self,
            *,
            user: AuthenticatedUser,
            chat_id: int,
            caller: Callable[..., Any],
            url_setting_name: str,
            label: str,
    ) -> DocumentQuestionRunResult:
        messages = await self._build_llm_messages(chat_id)
        system_prompt, response_style = await self._get_chat_prompt_style(chat_id)
        try:
            result: AgentRunResult = await caller(
                messages, user, chat_id=chat_id,
                system_prompt=system_prompt, response_style=response_style,
            )
        except HttpClientException as e:
            logger.error(
                "LLM %s failed: %s",
                label,
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_url": getattr(settings, url_setting_name, ""),
                },
                exc_info=True,
            )
            raise LLMServiceException() from e

        assistant_msg = await self._persist_ai_answer(
            chat_id, user.id, result.answer, result.fragments or None
        )
        return DocumentQuestionRunResult(
            question="",
            answer=result.answer,
            fragments=result.fragments,
            assistant_message=assistant_msg,
        )

    async def _persist_ai_answer(
            self,
            chat_id: int,
            user_id: int,
            answer: str,
            fragments: list | None,
    ) -> ArtifactMessage | None:
        if not answer or not answer.strip():
            return None
        assistant_msg = await sync_to_async(self._save_ai_message)(
            chat_id, user_id, answer, fragments
        )
        logger.info(
            "AI response saved.",
            extra={"chat_id": chat_id, "message_id": assistant_msg.id},
        )
        return assistant_msg

    def iter_ai_reply_stream_group_payloads(
            self,
            mode: str,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> AsyncIterator[dict[str, Any]]:
        if mode == ChatAIMode.GENERAL_CHAT:
            return self.iter_general_chat_stream_group_payloads(user, chat_id)
        if mode == ChatAIMode.RAG_AGENT:
            return self.iter_rag_agent_stream_group_payloads(user, chat_id)
        if mode == ChatAIMode.AGENT:
            return self.iter_agent_stream_group_payloads(user, chat_id)
        return self.iter_document_question_stream_group_payloads(user, chat_id)

    async def iter_document_question_stream_group_payloads(
            self,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> AsyncIterator[dict[str, Any]]:
        messages = await self._build_llm_messages(chat_id)
        system_prompt, response_style = await self._get_chat_prompt_style(chat_id)
        async for payload in self._iter_ai_stream_group_payloads(
                chat_id=chat_id,
                user=user,
                sse_events=llm_client.document_question_stream_events(
                    messages, user, chat_id=chat_id,
                    system_prompt=system_prompt, response_style=response_style,
                ),
                complete_extractor=self._extract_document_question_complete,
                stream_url_setting_name="LLM_DOCUMENT_QUESTION_STREAM_URL",
        ):
            yield payload

    async def iter_general_chat_stream_group_payloads(
            self,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> AsyncIterator[dict[str, Any]]:
        messages = await self._build_llm_messages(chat_id)
        system_prompt, response_style = await self._get_chat_prompt_style(chat_id)
        async for payload in self._iter_ai_stream_group_payloads(
                chat_id=chat_id,
                user=user,
                sse_events=llm_client.general_chat_stream_events(
                    messages, user, chat_id=chat_id,
                    system_prompt=system_prompt, response_style=response_style,
                ),
                complete_extractor=self._extract_general_chat_complete,
                stream_url_setting_name="LLM_GENERAL_CHAT_STREAM_URL",
        ):
            yield payload

    async def iter_rag_agent_stream_group_payloads(
            self,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> AsyncIterator[dict[str, Any]]:
        messages = await self._build_llm_messages(chat_id)
        system_prompt, response_style = await self._get_chat_prompt_style(chat_id)
        async for payload in self._iter_ai_stream_group_payloads(
                chat_id=chat_id,
                user=user,
                sse_events=llm_client.rag_agent_stream_events(
                    messages, user, chat_id=chat_id,
                    system_prompt=system_prompt, response_style=response_style,
                ),
                complete_extractor=self._extract_agent_complete,
                stream_url_setting_name="LLM_RAG_AGENT_STREAM_URL",
        ):
            yield payload

    async def iter_agent_stream_group_payloads(
            self,
            user: AuthenticatedUser,
            chat_id: int,
    ) -> AsyncIterator[dict[str, Any]]:
        messages = await self._build_llm_messages(chat_id)
        system_prompt, response_style = await self._get_chat_prompt_style(chat_id)
        async for payload in self._iter_ai_stream_group_payloads(
                chat_id=chat_id,
                user=user,
                sse_events=llm_client.agent_stream_events(
                    messages, user, chat_id=chat_id,
                    system_prompt=system_prompt, response_style=response_style,
                ),
                complete_extractor=self._extract_agent_complete,
                stream_url_setting_name="LLM_AGENT_STREAM_URL",
        ):
            yield payload

    async def _iter_ai_stream_group_payloads(
            self,
            *,
            chat_id: int,
            user: AuthenticatedUser,
            sse_events: AsyncIterator[dict[str, Any]],
            complete_extractor: Callable[
                [dict[str, Any], str, str, list[Any]], tuple[str, str, list[Any]]
            ],
            stream_url_setting_name: str,
    ) -> AsyncIterator[dict[str, Any]]:
        accumulated_answer = ""
        received_complete = False
        last_question = ""
        last_fragments: list[Any] = []

        async def _build_and_save_complete() -> dict[str, Any] | None:
            answer = accumulated_answer.strip()
            if not answer:
                return None
            assistant_msg: ArtifactMessage | None = None
            try:
                assistant_msg = await sync_to_async(self._save_ai_message)(
                    chat_id, user.id, answer, last_fragments or None
                )
                logger.info(
                    "AI response saved (stream fallback).",
                    extra={"chat_id": chat_id, "message_id": assistant_msg.id},
                )
            except Exception:
                logger.exception(
                    "Failed to save fallback AI message.",
                    extra={"chat_id": chat_id},
                )
            event: dict[str, Any] = {
                "type": "ai_complete",
                "message": answer,
                "answer": answer,
                "question": last_question,
                "fragments": last_fragments,
            }
            if assistant_msg:
                event["id"] = assistant_msg.id
                event["sender_type"] = assistant_msg.sender_type
                event["created_by"] = assistant_msg.created_by
                event["created_at"] = assistant_msg.created_at.isoformat()
            return event

        try:
            async for sse in sse_events:
                et = sse.get("type")
                if et == "meta":
                    last_question = str(sse.get("question", ""))
                    last_fragments = llm_client.normalize_fragments(sse.get("fragments"))
                    yield {
                        "type": "ai_context",
                        "question": last_question,
                        "fragments": last_fragments,
                    }
                elif et == "progress":
                    yield {
                        "type": "ai_progress",
                        "step": str(sse.get("step", "")),
                        "message": str(sse.get("message", "")),
                    }
                elif et == "delta":
                    delta = str(sse.get("text", ""))
                    accumulated_answer += delta
                    yield {
                        "type": "ai_delta",
                        "delta": delta,
                    }
                elif et == "complete":
                    received_complete = True
                    result = sse.get("result") or {}
                    if not isinstance(result, dict):
                        result = {}
                    q, answer, fragments = complete_extractor(
                        result, accumulated_answer, last_question, last_fragments
                    )

                    assistant_msg: ArtifactMessage | None = None
                    if answer:
                        assistant_msg = await sync_to_async(self._save_ai_message)(
                            chat_id, user.id, answer, fragments or None
                        )
                        logger.info(
                            "AI response saved (stream).",
                            extra={
                                "chat_id": chat_id,
                                "message_id": assistant_msg.id,
                            },
                        )

                    event: dict[str, Any] = {
                        "type": "ai_complete",
                        "message": answer,
                        "answer": answer,
                        "question": q,
                        "fragments": fragments,
                    }
                    if assistant_msg:
                        event["id"] = assistant_msg.id
                        event["sender_type"] = assistant_msg.sender_type
                        event["created_by"] = assistant_msg.created_by
                        event["created_at"] = assistant_msg.created_at.isoformat()
                    yield event
                elif et == "error":
                    yield {
                        "type": "ai_error",
                        "detail": str(sse.get("message", "AI error")),
                        "code": sse.get("code"),
                    }
                    return
        except HttpClientException as e:
            logger.error(
                "LLM stream failed: %s",
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_stream_url": getattr(settings, stream_url_setting_name, ""),
                },
                exc_info=True,
            )
            fallback = await _build_and_save_complete()
            if fallback:
                yield fallback
                return
            raise LLMServiceException() from e

        if not received_complete:
            fallback = await _build_and_save_complete()
            if fallback:
                yield fallback

    @staticmethod
    def _extract_document_question_complete(
            result: dict[str, Any],
            accumulated_answer: str,
            last_question: str,
            last_fragments: list[Any],
    ) -> tuple[str, str, list[Any]]:
        question = str(result.get("question", "")).strip() or last_question
        answer = str(result.get("answer", "")).strip() or accumulated_answer.strip()
        fragments = llm_client.normalize_fragments(result.get("fragments")) or last_fragments
        return question, answer, fragments

    @staticmethod
    def _extract_general_chat_complete(
            result: dict[str, Any],
            accumulated_answer: str,
            last_question: str,
            last_fragments: list[Any],
    ) -> tuple[str, str, list[Any]]:
        answer = str(result.get("answer", "")).strip() or accumulated_answer.strip()
        return "", answer, []

    @staticmethod
    def _extract_agent_complete(
            result: dict[str, Any],
            accumulated_answer: str,
            last_question: str,
            last_fragments: list[Any],
    ) -> tuple[str, str, list[Any]]:
        answer = ""
        messages = result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                if isinstance(message, dict) and message.get("role") == "assistant":
                    answer = str(message.get("content", "")).strip()
                    break
        answer = answer or accumulated_answer.strip()
        fragments = llm_client.normalize_fragments(result.get("fragments")) or last_fragments
        return "", answer, fragments

    @staticmethod
    async def _get_chat_prompt_style(chat_id: int) -> tuple[str | None, str | None]:
        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            return None, None
        system_prompt = getattr(chat, "system_prompt", None) or None
        response_style = getattr(chat, "response_style", None) or None
        return system_prompt, response_style

    def delete_message(self, user: AuthenticatedUser, chat_id: int, message_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({DELETE_MESSAGE}))
        self._require_access(chat_id, user.id)
        msg = message_repository.get_by_id_and_chat(message_id, chat_id)
        if msg is None:
            raise MessageNotFoundException()
        if not membership_repository.is_chat_owner(chat_id, user.id):
            raise MessageDeleteForbiddenException()
        msg.delete(deleted_by=user.id)
        logger.info("Message deleted.", extra={"chat_id": chat_id, "message_id": message_id, "user_id": user.id})

    def _require_access(self, chat_id: int, user_id: int):
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user_id):
            raise MessageAccessDeniedException()
        return chat

    def _require_send_access(self, chat_id: int, user_id: int):
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        role = membership_repository.get_role(chat_id, user_id)
        if role is None:
            raise MessageAccessDeniedException()
        if role == "reader":
            raise ReaderCannotSendMessageException()
        if chat.is_locked:
            raise ChatLockedException()
        return chat

    def assert_send_access(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({SEND_MESSAGE}))
        return self._require_send_access(chat_id, user.id)


message_service = MessageService()
