import logging
from typing import Optional

from apps.artifact.exceptions import (
    ArtifactAccessDeniedException,
    ArtifactNotFoundException,
    UnknownArtifactTypeException,
)
from apps.artifact.models import Artifact
from apps.artifact.registry import is_known_type
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.artifact.repositories.artifact_version_repository import artifact_version_repository
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import permissions as perms
from core.authorization.access import AccessControl

logger = logging.getLogger(__name__)


def _assert_artifact_access(user_id: int, artifact: Artifact, *, require_contributor: bool = False) -> None:
    if artifact.created_by == user_id:
        return
    checker = (
        membership_repository.is_active_contributor
        if require_contributor
        else membership_repository.is_active_member
    )
    if checker(artifact.source_chat_id, user_id):
        return
    raise ArtifactAccessDeniedException()


class ArtifactService:
    def list_artifacts(
        self,
        user: AuthenticatedUser,
        artifact_type: Optional[str] = None,
        chat_id: Optional[int] = None,
    ):
        AccessControl.require_permissions(user, frozenset({perms.LIST_ARTIFACTS}))
        if artifact_type is not None and not is_known_type(artifact_type):
            raise UnknownArtifactTypeException()
        if chat_id is not None:
            if chat_repository.get_by_id(chat_id) is None:
                raise ChatNotFoundException()
            if not membership_repository.is_active_member(chat_id, user.id):
                raise ChatAccessDeniedException()
            return artifact_repository.list_by_chat(source_chat_id=chat_id, artifact_type=artifact_type)
        return artifact_repository.list_by_user(user_id=user.id, artifact_type=artifact_type)

    def list_all_artifacts(self, user: AuthenticatedUser, artifact_type: Optional[str] = None):
        AccessControl.require_permissions(user, frozenset({perms.MANAGE_ARTIFACTS}))
        if artifact_type is not None and not is_known_type(artifact_type):
            raise UnknownArtifactTypeException()
        return artifact_repository.list_all(artifact_type=artifact_type)

    def get_artifact(self, user: AuthenticatedUser, artifact_id: int) -> Artifact:
        AccessControl.require_permissions(user, frozenset({perms.GET_ARTIFACT}))
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundException()
        _assert_artifact_access(user.id, artifact)
        return artifact

    def create_artifact(
        self,
        user: AuthenticatedUser,
        *,
        type: str,
        source_chat_id: int,
        title: str = "",
        description: str = "",
        status: str = Artifact.Status.DRAFT,
        mode: str = Artifact.Mode.DIRECT,
    ) -> Artifact:
        AccessControl.require_permissions(user, frozenset({perms.CREATE_ARTIFACT}))
        if not is_known_type(type):
            raise UnknownArtifactTypeException()
        if chat_repository.get_by_id(source_chat_id) is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_contributor(source_chat_id, user.id):
            raise ChatAccessDeniedException()
        artifact = artifact_repository.create(
            user_id=user.id,
            type=type,
            title=title,
            description=description,
            status=status,
            mode=mode,
            source_chat_id=source_chat_id,
        )
        logger.info(
            "Artifact created",
            extra={"user_id": user.id, "artifact_id": artifact.id, "type": type},
        )
        return artifact

    def update_artifact(
        self,
        user: AuthenticatedUser,
        artifact_id: int,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        mode: Optional[str] = None,
        change_summary: str = "",
    ) -> Artifact:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_ARTIFACT}))
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundException()
        _assert_artifact_access(user.id, artifact, require_contributor=True)
        return artifact_repository.update(
            artifact,
            updated_by=user.id,
            title=title,
            description=description,
            status=status,
            mode=mode,
            change_summary=change_summary,
        )

    def delete_artifact(self, user: AuthenticatedUser, artifact_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_ARTIFACT}))
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundException()
        _assert_artifact_access(user.id, artifact, require_contributor=True)
        artifact_repository.soft_delete(artifact, deleted_by=user.id)
        logger.info("Artifact deleted", extra={"user_id": user.id, "artifact_id": artifact_id})

    def list_versions(self, user: AuthenticatedUser, artifact_id: int):
        AccessControl.require_permissions(user, frozenset({perms.LIST_ARTIFACT_VERSIONS}))
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundException()
        _assert_artifact_access(user.id, artifact)
        return artifact_version_repository.list_for_artifact(artifact_id)


artifact_service = ArtifactService()
