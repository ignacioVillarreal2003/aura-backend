from django.db.models import QuerySet
from rest_framework.exceptions import PermissionDenied

from apps.artifact.models.artifact_thread_reply import ArtifactThreadReply
from apps.artifact.repositories.artifact_thread_reply_repository import thread_repository
from apps.artifact.services.artifact_access import require_interaction_access
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import ADD_THREAD_REPLY, DELETE_THREAD_REPLY, EDIT_THREAD_REPLY, LIST_THREAD_REPLIES


class ThreadService:
    def get_thread(self, user: AuthenticatedUser, artifact_id: int) -> QuerySet[ArtifactThreadReply]:
        AccessControl.require_permissions(user, frozenset({LIST_THREAD_REPLIES}))
        require_interaction_access(user.id, artifact_id)
        return thread_repository.get_by_artifact(artifact_id)

    def add_reply(self, user: AuthenticatedUser, artifact_id: int, message_text: str) -> ArtifactThreadReply:
        AccessControl.require_permissions(user, frozenset({ADD_THREAD_REPLY}))
        require_interaction_access(user.id, artifact_id)
        return thread_repository.create(
            parent_artifact_id=artifact_id,
            message=message_text,
            created_by=user.id,
        )

    def update_reply(
        self, user: AuthenticatedUser, artifact_id: int, reply_id: int, message_text: str
    ) -> ArtifactThreadReply:
        AccessControl.require_permissions(user, frozenset({EDIT_THREAD_REPLY}))
        require_interaction_access(user.id, artifact_id)
        reply = thread_repository.get_by_id(reply_id)
        if reply is None or reply.parent_artifact_id != artifact_id:
            from rest_framework.exceptions import NotFound
            raise NotFound("Respuesta no encontrada.")
        if reply.created_by != user.id:
            raise PermissionDenied("Solo podés editar tus propias respuestas.")
        return thread_repository.update(reply, message_text, updated_by=user.id)

    def delete_reply(self, user: AuthenticatedUser, artifact_id: int, reply_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({DELETE_THREAD_REPLY}))
        require_interaction_access(user.id, artifact_id)
        reply = thread_repository.get_by_id(reply_id)
        if reply is None or reply.parent_artifact_id != artifact_id:
            from rest_framework.exceptions import NotFound
            raise NotFound("Respuesta no encontrada.")
        if reply.created_by != user.id:
            raise PermissionDenied("Solo podés eliminar tus propias respuestas.")
        thread_repository.soft_delete(reply, deleted_by=user.id)


thread_service = ThreadService()
