import logging
from django.db.models import QuerySet

from apps.artifact.models.artifact_pin import ArtifactPin
from apps.artifact.repositories.artifact_pin_repository import pin_repository
from apps.artifact.services.artifact_access import require_interaction_access
from apps.membership.repositories.membership_repository import membership_repository
from apps.artifact_message.exceptions import MessageAccessDeniedException, NotChatOwnerException
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import LIST_PINNED_MESSAGES, PIN_MESSAGE

logger = logging.getLogger(__name__)


class PinService:
    def list_pinned(self, user: AuthenticatedUser, chat_id: int) -> QuerySet[ArtifactPin]:
        AccessControl.require_permissions(user, frozenset({LIST_PINNED_MESSAGES}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        return pin_repository.list_by_chat(chat_id)

    def pin(self, user: AuthenticatedUser, artifact_id: int) -> ArtifactPin:
        AccessControl.require_permissions(user, frozenset({PIN_MESSAGE}))
        chat_id = self._require_chat_owner(user, artifact_id)
        pin, _ = pin_repository.pin(artifact_id, created_by=user.id)
        logger.info("Artifact pinned.", extra={"chat_id": chat_id, "artifact_id": artifact_id, "user_id": user.id})
        return pin

    def unpin(self, user: AuthenticatedUser, artifact_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({PIN_MESSAGE}))
        chat_id = self._require_chat_owner(user, artifact_id)
        pin_repository.unpin(artifact_id)
        logger.info("Artifact unpinned.", extra={"chat_id": chat_id, "artifact_id": artifact_id, "user_id": user.id})

    @staticmethod
    def _require_chat_owner(user: AuthenticatedUser, artifact_id: int) -> int:
        artifact = require_interaction_access(user.id, artifact_id)
        chat_id = artifact.source_chat_id
        if not membership_repository.is_chat_owner(chat_id, user.id):
            raise NotChatOwnerException()
        return chat_id


pin_service = PinService()
