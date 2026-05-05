import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import LLMServiceException, MessageAccessDeniedException, TranscriptionException
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository
from apps.message.serializers.response import MessageResponse
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import LIST_MESSAGES, SEND_MESSAGE
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import DocumentQuestionResult, llm_client
from core.clients.transcription_client import transcription_client

logger = logging.getLogger(__name__)


def _broadcast_user_message_to_chat_group(chat_id: int, msg: ChatMessage) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    payload = MessageResponse(msg).data
    async_to_sync(channel_layer.group_send)(
        f"chat_{chat_id}",
        {"type": "user_message", **payload},
    )


def broadcast_chat_ai_lock_change(chat_id: int, locked: bool) -> None:
    """Tell all subscribers whether new user messages are accepted (AI turn in progress)."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"chat_{chat_id}",
        {"type": "chat_ai_lock_changed", "locked": locked},
    )


@dataclass
class DocumentQuestionRunResult:
    question: str
    answer: str
    fragments: list[dict[str, Any]]
    assistant_message: ChatMessage | None = None


class MessageService:
    def transcribe_audio(self, audio_file) -> str:
        try:
            return transcription_client.transcribe(audio_file)
        except Exception as e:
            raise TranscriptionException() from e

    def send_message(
        self,
        user: AuthenticatedUser,
        chat_id: int,
        text: str,
    ) -> ChatMessage:
        AccessControl.require_permissions(user, frozenset({SEND_MESSAGE}))
        self._require_access(chat_id, user.id)

        with transaction.atomic():
            msg = message_repository.create(
                chat_id=chat_id,
                message=text,
                sender_type=ChatMessage.SenderType.USER,
                created_by=user.id,
            )
            chat = chat_repository.get_by_id(chat_id)
            if chat:
                chat_repository.update(
                    chat, updated_by=user.id, last_message_at=timezone.now()
                )

        logger.info(
            "User message saved.",
            extra={"chat_id": chat_id, "message_id": msg.id, "user_id": user.id},
        )
        _broadcast_user_message_to_chat_group(chat_id, msg)
        return msg

    def _save_ai_message(self, chat_id: int, user_id: int, answer: str) -> ChatMessage:
        with transaction.atomic():
            msg = message_repository.create(
                chat_id=chat_id,
                message=answer,
                sender_type=ChatMessage.SenderType.SYSTEM,
                created_by=user_id,
            )
            chat = chat_repository.get_by_id(chat_id)
            if chat:
                chat_repository.update(
                    chat, updated_by=user_id, last_message_at=timezone.now()
                )
        return msg

    def get_messages(self, user: AuthenticatedUser, chat_id: int):
        AccessControl.require_permissions(user, frozenset({LIST_MESSAGES}))
        self._require_access(chat_id, user.id)
        return message_repository.get_messages_by_chat(chat_id)

    @staticmethod
    async def _build_llm_messages(chat_id: int) -> list[dict[str, str]]:
        limit = getattr(settings, "LLM_CONTEXT_MESSAGE_LIMIT", 20)
        recent = await sync_to_async(message_repository.get_recent_messages)(
            chat_id, limit=limit
        )
        messages: list[dict[str, str]] = []
        for m in reversed(recent):
            if m.sender_type == ChatMessage.SenderType.USER:
                messages.append({"role": "human", "content": m.message})
            elif m.sender_type == ChatMessage.SenderType.SYSTEM:
                messages.append({"role": "assistant", "content": m.message})
        return messages

    async def run_document_question(
        self,
        user: AuthenticatedUser,
        chat_id: int,
    ) -> DocumentQuestionRunResult:
        await sync_to_async(self._require_access)(chat_id, user.id)

        messages = await self._build_llm_messages(chat_id)

        try:
            llm_out: DocumentQuestionResult = await llm_client.document_question(
                messages, user
            )
        except HttpClientException as e:
            logger.error(
                "LLM document-question failed: %s",
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_url": getattr(
                        settings, "LLM_DOCUMENT_QUESTION_URL", ""
                    ),
                },
                exc_info=True,
            )
            raise LLMServiceException() from e

        assistant_msg: ChatMessage | None = None
        if llm_out.answer.strip():
            assistant_msg = await sync_to_async(self._save_ai_message)(
                chat_id, user.id, llm_out.answer
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

    async def iter_document_question_stream_group_payloads(
        self,
        user: AuthenticatedUser,
        chat_id: int,
    ) -> AsyncIterator[dict[str, Any]]:
        await sync_to_async(self._require_access)(chat_id, user.id)

        messages = await self._build_llm_messages(chat_id)

        try:
            async for sse in llm_client.document_question_stream_events(
                messages, user
            ):
                et = sse.get("type")
                if et == "meta":
                    yield {
                        "type": "ai_context",
                        "question": str(sse.get("question", "")),
                        "fragments": llm_client.normalize_fragments(
                            sse.get("fragments")
                        ),
                    }
                elif et == "delta":
                    yield {
                        "type": "ai_delta",
                        "delta": str(sse.get("text", "")),
                    }
                elif et == "complete":
                    result = sse.get("result") or {}
                    if not isinstance(result, dict):
                        result = {}
                    q = str(result.get("question", ""))
                    answer = str(result.get("answer", "")).strip()
                    fragments = llm_client.normalize_fragments(
                        result.get("fragments")
                    )

                    assistant_msg: ChatMessage | None = None
                    if answer:
                        assistant_msg = await sync_to_async(self._save_ai_message)(
                            chat_id, user.id, answer
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
                "LLM document-question stream failed: %s",
                str(e),
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "status_code": e.status_code,
                    "llm_stream_url": getattr(
                        settings, "LLM_DOCUMENT_QUESTION_STREAM_URL", ""
                    ),
                },
                exc_info=True,
            )
            raise LLMServiceException() from e

    def _require_access(self, chat_id: int, user_id: int) -> None:
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if not membership_repository.is_active_member(chat_id, user_id):
            raise MessageAccessDeniedException()


message_service = MessageService()
