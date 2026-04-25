import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import LLMServiceException, MessageAccessDeniedException
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import DocumentQuestionResult, llm_client

logger = logging.getLogger(__name__)


@dataclass
class DocumentQuestionRunResult:
    question: str
    answer: str
    fragments: list[dict[str, Any]]
    assistant_message: ChatMessage | None = None


class MessageService:

    def send_message(
        self,
        user: AuthenticatedUser,
        chat_id: int,
        text: str,
    ) -> ChatMessage:
        self._require_access(chat_id, user.id)

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
        return msg

    def get_messages(self, user: AuthenticatedUser, chat_id: int):
        self._require_access(chat_id, user.id)
        return message_repository.get_messages_by_chat(chat_id)

    async def run_document_question(
        self,
        user: AuthenticatedUser,
        chat_id: int,
    ) -> DocumentQuestionRunResult:
        await sync_to_async(self._require_access)(chat_id, user.id)

        recent = await sync_to_async(message_repository.get_recent_messages)(
            chat_id, limit=20
        )
        messages: list[dict[str, str]] = []
        for m in reversed(recent):
            if m.sender_type == ChatMessage.SenderType.USER:
                messages.append({"role": "human", "content": m.message})
            elif m.sender_type == ChatMessage.SenderType.SYSTEM:
                messages.append({"role": "assistant", "content": m.message})

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
            assistant_msg = await sync_to_async(message_repository.create)(
                chat_id=chat_id,
                message=llm_out.answer,
                sender_type=ChatMessage.SenderType.SYSTEM,
                created_by=user.id,
            )
            chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
            if chat:
                await sync_to_async(chat_repository.update)(
                    chat, updated_by=user.id, last_message_at=timezone.now()
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
        """
        Yields dicts suitable for ``channel_layer.group_send`` (must include ``type``
        matching a ``ChatConsumer`` handler: ``ai_context``, ``ai_delta``,
        ``ai_complete``, ``ai_error``).
        """
        await sync_to_async(self._require_access)(chat_id, user.id)

        recent = await sync_to_async(message_repository.get_recent_messages)(
            chat_id, limit=20
        )
        messages: list[dict[str, str]] = []
        for m in reversed(recent):
            if m.sender_type == ChatMessage.SenderType.USER:
                messages.append({"role": "human", "content": m.message})
            elif m.sender_type == ChatMessage.SenderType.SYSTEM:
                messages.append({"role": "assistant", "content": m.message})

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
                        assistant_msg = await sync_to_async(
                            message_repository.create
                        )(
                            chat_id=chat_id,
                            message=answer,
                            sender_type=ChatMessage.SenderType.SYSTEM,
                            created_by=user.id,
                        )
                        chat = await sync_to_async(chat_repository.get_by_id)(
                            chat_id
                        )
                        if chat:
                            await sync_to_async(chat_repository.update)(
                                chat,
                                updated_by=user.id,
                                last_message_at=timezone.now(),
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
