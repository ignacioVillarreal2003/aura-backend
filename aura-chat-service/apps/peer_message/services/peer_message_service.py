import logging

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.peer_message.exceptions import (
    PeerChatAccessDeniedException,
    PeerMessageForbiddenException,
    PeerMessageNotFoundException,
)
from apps.peer_message.models import PeerMessage
from apps.peer_message.repositories.peer_message_repository import peer_message_repository
from apps.peer_message.serializers.response import PeerMessageResponse
from core.authentication.authenticated_user import AuthenticatedUser
from core.ws.group_broadcast import send_to_chat_group

logger = logging.getLogger(__name__)


def _broadcast_message(chat_id: int, event_type: str, msg: PeerMessage) -> None:
    send_to_chat_group(chat_id, {"type": event_type, **PeerMessageResponse(msg).data})


class PeerMessageService:
    """Human-to-human side channel for a chat. Access is gated only by active
    membership in the parent chat (no AI, no permissions, no locks)."""

    def _require_member(self, chat_id: int, user_id: int):
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user_id):
            raise PeerChatAccessDeniedException()
        return chat

    def create(self, user: AuthenticatedUser, chat_id: int, text: str) -> PeerMessage:
        self._require_member(chat_id, user.id)
        msg = peer_message_repository.create(
            chat_id=chat_id, message=text, created_by=user.id
        )
        logger.info(
            "Peer message created.",
            extra={"chat_id": chat_id, "peer_message_id": msg.id, "user_id": user.id},
        )
        _broadcast_message(chat_id, "peer_message_created", msg)
        return msg

    def list(self, user: AuthenticatedUser, chat_id: int):
        self._require_member(chat_id, user.id)
        return peer_message_repository.list_by_chat(chat_id)

    def get(self, user: AuthenticatedUser, chat_id: int, message_id: int) -> PeerMessage:
        self._require_member(chat_id, user.id)
        msg = peer_message_repository.get_by_id_and_chat(message_id, chat_id)
        if msg is None:
            raise PeerMessageNotFoundException()
        return msg

    def update(
            self, user: AuthenticatedUser, chat_id: int, message_id: int, text: str
    ) -> PeerMessage:
        self._require_member(chat_id, user.id)
        msg = peer_message_repository.get_by_id_and_chat(message_id, chat_id)
        if msg is None:
            raise PeerMessageNotFoundException()
        # Only the author can edit their own message.
        if msg.created_by != user.id:
            raise PeerMessageForbiddenException()
        msg.message = text
        msg.updated_by = user.id
        # AuditModel.save auto-stamps updated_at when it is not in update_fields.
        msg.save(update_fields=["message", "updated_by"])
        logger.info(
            "Peer message edited.",
            extra={"chat_id": chat_id, "peer_message_id": msg.id, "user_id": user.id},
        )
        _broadcast_message(chat_id, "peer_message_updated", msg)
        return msg

    def delete(self, user: AuthenticatedUser, chat_id: int, message_id: int) -> None:
        self._require_member(chat_id, user.id)
        msg = peer_message_repository.get_by_id_and_chat(message_id, chat_id)
        if msg is None:
            raise PeerMessageNotFoundException()
        # The author can delete their own message; the chat owner can moderate any.
        if msg.created_by != user.id and not membership_repository.is_chat_owner(
                chat_id, user.id
        ):
            raise PeerMessageForbiddenException()
        msg.delete(deleted_by=user.id)
        logger.info(
            "Peer message deleted.",
            extra={"chat_id": chat_id, "peer_message_id": message_id, "user_id": user.id},
        )
        send_to_chat_group(
            chat_id,
            {"type": "peer_message_deleted", "id": message_id, "deleted_by": user.id},
        )


peer_message_service = PeerMessageService()
