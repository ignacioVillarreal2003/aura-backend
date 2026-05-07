import logging
import uuid

from django.db.models import QuerySet
from django.utils import timezone

from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException, ShareLinkExpiredOrInactiveException, ShareLinkNotFoundException
from apps.chat.models.chat_share_link import ChatShareLink
from apps.chat.repositories.chat_repository import chat_repository
from apps.chat.repositories.share_link_repository import share_link_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.repositories.message_repository import message_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import CREATE_SHARE_LINK, DELETE_SHARE_LINK, LIST_SHARE_LINKS

logger = logging.getLogger(__name__)


class ShareLinkService:
    def create_link(
        self,
        user: AuthenticatedUser,
        chat_id: int,
        expires_at=None,
    ) -> ChatShareLink:
        AccessControl.require_permissions(user, frozenset({CREATE_SHARE_LINK}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can create share links")
        link = share_link_repository.create(
            chat_id=chat_id,
            created_by=user.id,
            expires_at=expires_at,
        )
        logger.info("Share link created.", extra={"chat_id": chat_id, "link_id": link.id, "user_id": user.id})
        return link

    def list_links(self, user: AuthenticatedUser, chat_id: int) -> QuerySet[ChatShareLink]:
        AccessControl.require_permissions(user, frozenset({LIST_SHARE_LINKS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can list share links")
        return share_link_repository.list_by_chat(chat_id)

    def revoke_link(self, user: AuthenticatedUser, chat_id: int, link_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({DELETE_SHARE_LINK}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if chat.created_by != user.id:
            raise ChatAccessDeniedException("Only the chat owner can revoke share links")
        link = share_link_repository.get_by_id(link_id, chat_id)
        if link is None:
            raise ShareLinkNotFoundException()
        share_link_repository.deactivate(link)
        logger.info("Share link revoked.", extra={"chat_id": chat_id, "link_id": link_id, "user_id": user.id})

    def get_public_messages(self, token: uuid.UUID):
        link = share_link_repository.get_by_token(token)
        if link is None:
            raise ShareLinkNotFoundException()
        if not link.is_active:
            raise ShareLinkExpiredOrInactiveException()
        if link.expires_at is not None and link.expires_at < timezone.now():
            raise ShareLinkExpiredOrInactiveException()
        return message_repository.get_messages_by_chat(link.chat_id)


share_link_service = ShareLinkService()
