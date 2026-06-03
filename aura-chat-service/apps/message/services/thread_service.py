from django.db.models import QuerySet

from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException
from apps.message.models.message_thread_reply import ArtifactThreadReply
from apps.message.repositories.thread_repository import thread_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import ADD_THREAD_REPLY, LIST_THREAD_REPLIES


class ThreadService:
    def get_thread(
            self, user: AuthenticatedUser, chat_id: int, artifact_id: int
    ) -> QuerySet[ArtifactThreadReply]:
        AccessControl.require_permissions(user, frozenset({LIST_THREAD_REPLIES}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None or artifact.source_chat_id != chat_id:
            raise MessageNotFoundException()
        return thread_repository.get_by_artifact(artifact_id)

    def add_reply(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            artifact_id: int,
            message_text: str,
    ) -> ArtifactThreadReply:
        AccessControl.require_permissions(user, frozenset({ADD_THREAD_REPLY}))
        if not membership_repository.is_active_member(chat_id, user.id):
            raise MessageAccessDeniedException()
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None or artifact.source_chat_id != chat_id:
            raise MessageNotFoundException()
        return thread_repository.create(
            parent_artifact_id=artifact_id,
            message=message_text,
            created_by=user.id,
        )


thread_service = ThreadService()
