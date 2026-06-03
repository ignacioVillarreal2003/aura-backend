import logging
from django.db.models import QuerySet

from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException, NotChatOwnerException
from apps.message.models.pinned_message import ArtifactPin
from apps.message.repositories.pinned_message_repository import pinned_message_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import LIST_PINNED_MESSAGES, PIN_MESSAGE

logger = logging.getLogger(__name__)


class PinnedMessageService:
    def list_pinned(self, user: AuthenticatedUser, chat_id: int) -> QuerySet[ArtifactPin]:
        AccessControl.require_permissions(user, frozenset({LIST_PINNED_MESSAGES}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        return pinned_message_repository.list_by_chat(chat_id)

    def pin_message(self, user: AuthenticatedUser, chat_id: int, artifact_id: int) -> ArtifactPin:
        AccessControl.require_permissions(user, frozenset({PIN_MESSAGE}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        if not membership_repository.is_chat_owner(chat_id, user.id):
            raise NotChatOwnerException()
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None or artifact.source_chat_id != chat_id:
            raise MessageNotFoundException()
        pin, _ = pinned_message_repository.pin(artifact_id, chat_id, pinned_by=user.id)
        logger.info("Artifact pinned.", extra={"chat_id": chat_id, "artifact_id": artifact_id, "user_id": user.id})
        return pin

    def unpin_message(self, user: AuthenticatedUser, chat_id: int, artifact_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({PIN_MESSAGE}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        if not membership_repository.is_chat_owner(chat_id, user.id):
            raise NotChatOwnerException()
        pinned_message_repository.unpin(artifact_id, chat_id)
        logger.info("Artifact unpinned.", extra={"chat_id": chat_id, "artifact_id": artifact_id, "user_id": user.id})


pinned_message_service = PinnedMessageService()
