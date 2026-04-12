import logging
from dataclasses import dataclass
from typing import Any

from asgiref.sync import sync_to_async
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
    """LLM output plus optional persisted assistant row."""

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
                "LLM document-question failed.",
                extra={"chat_id": chat_id, "error": str(e)},
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

    def _require_access(self, chat_id: int, user_id: int) -> None:
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()

        if not membership_repository.is_active_member(chat_id, user_id):
            raise MessageAccessDeniedException()


message_service = MessageService()
