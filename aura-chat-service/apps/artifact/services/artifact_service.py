import logging
from datetime import datetime
from typing import Optional
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from apps.artifact.broadcasting import broadcast_artifact_deleted, broadcast_artifact_updated
from apps.artifact.exceptions import (
    ArtifactAccessDeniedException,
    ArtifactCreationFailedException,
    ArtifactNotFoundException,
    UnknownArtifactTypeException,
)
from apps.artifact.models import Artifact, ArtifactBookmark, ArtifactFeedback, ArtifactPin, ArtifactThreadReply
from apps.artifact.registry import is_known_type
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.artifact.repositories.artifact_version_repository import artifact_version_repository
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import permissions as perms
from core.authorization.access import AccessControl
from core.authorization.permissions import MANAGE_CHAT_ARTIFACTS

logger = logging.getLogger(__name__)

_DETAIL_RELATIONS = {
    Artifact.Type.MESSAGE: "message_content",
    Artifact.Type.REPORT: "report_content",
    Artifact.Type.CHECKLIST: "checklist_content",
    Artifact.Type.QUIZ: "quiz_content",
    Artifact.Type.TIMELINE: "timeline_content",
    Artifact.Type.LESSONS_LEARNED: "lessons_learned_content",
    Artifact.Type.DECISION_BRIEF: "decision_brief_content",
}


def _soft_delete_detail(artifact: Artifact, deleted_by: int) -> None:
    attr = _DETAIL_RELATIONS.get(artifact.type)
    if attr is None:
        return
    try:
        detail = getattr(artifact, attr)
    except ObjectDoesNotExist:
        return
    detail.delete(deleted_by=deleted_by)


def _cleanup_artifact_interactions(artifact_id: int) -> None:
    ArtifactPin.objects.filter(artifact_id=artifact_id).delete()
    ArtifactBookmark.objects.filter(artifact_id=artifact_id).delete()
    ArtifactFeedback.objects.filter(artifact_id=artifact_id).delete()
    ArtifactThreadReply.objects.filter(parent_artifact_id=artifact_id).delete()


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

    def list_chat_artifacts(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            artifact_type: Optional[str] = None,
            created_by: Optional[int] = None,
            date_from: Optional[datetime] = None,
            date_to: Optional[datetime] = None,
    ):
        AccessControl.require_permissions(user, frozenset({perms.LIST_ARTIFACTS}))
        if artifact_type is not None and not is_known_type(artifact_type):
            raise UnknownArtifactTypeException()
        if chat_repository.get_by_id(chat_id) is None:
            raise ChatNotFoundException()
        if not membership_repository.is_active_member(chat_id, user.id):
            raise ChatAccessDeniedException()
        return artifact_repository.list_by_chat_filtered(
            source_chat_id=chat_id,
            artifact_type=artifact_type,
            created_by=created_by,
            date_from=date_from,
            date_to=date_to,
        )

    def list_chat_artifacts_admin(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            artifact_type: Optional[str] = None,
            created_by: Optional[int] = None,
            date_from: Optional[datetime] = None,
            date_to: Optional[datetime] = None,
    ):
        AccessControl.require_permissions(user, frozenset({MANAGE_CHAT_ARTIFACTS}))
        if artifact_type is not None and not is_known_type(artifact_type):
            raise UnknownArtifactTypeException()
        if chat_repository.get_by_id(chat_id) is None:
            raise ChatNotFoundException()
        return artifact_repository.list_all_for_chat_filtered(
            source_chat_id=chat_id,
            artifact_type=artifact_type,
            created_by=created_by,
            date_from=date_from,
            date_to=date_to,
        )

    def get_artifact(self, user: AuthenticatedUser, artifact_id: int) -> Artifact:
        AccessControl.require_permissions(user, frozenset({perms.GET_ARTIFACT}))
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundException()
        _assert_artifact_access(user.id, artifact)
        return artifact

    @transaction.atomic
    def update_artifact(
            self,
            user: AuthenticatedUser,
            artifact_id: int,
            *,
            title: Optional[str] = None,
            description: Optional[str] = None,
            status: Optional[str] = None,
            change_summary: str = "",
    ) -> Artifact:
        AccessControl.require_permissions(user, frozenset({perms.UPDATE_ARTIFACT}))
        artifact = artifact_repository.get_by_id_for_update(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundException()
        _assert_artifact_access(user.id, artifact, require_contributor=True)
        artifact = artifact_repository.update(
            artifact,
            updated_by=user.id,
            title=title,
            description=description,
            status=status,
            change_summary=change_summary,
        )
        if artifact.source_chat_id:
            chat_id = artifact.source_chat_id
            artifact_snapshot = artifact
            transaction.on_commit(lambda: broadcast_artifact_updated(chat_id, artifact_snapshot))
        return artifact

    @transaction.atomic
    def delete_artifact(self, user: AuthenticatedUser, artifact_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({perms.DELETE_ARTIFACT}))
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundException()
        _assert_artifact_access(user.id, artifact, require_contributor=True)
        chat_id = artifact.source_chat_id
        _soft_delete_detail(artifact, deleted_by=user.id)
        _cleanup_artifact_interactions(artifact.id)
        artifact_repository.soft_delete(artifact, deleted_by=user.id)
        logger.info("Artifact deleted", extra={"user_id": user.id, "artifact_id": artifact_id})
        if chat_id:
            broadcast_artifact_deleted(chat_id, artifact_id, deleted_by=user.id)

    def list_versions(self, user: AuthenticatedUser, artifact_id: int):
        AccessControl.require_permissions(user, frozenset({perms.LIST_ARTIFACT_VERSIONS}))
        artifact = artifact_repository.get_by_id(artifact_id)
        if artifact is None:
            raise ArtifactNotFoundException()
        _assert_artifact_access(user.id, artifact)
        return artifact_version_repository.list_for_artifact(artifact_id)


artifact_service = ArtifactService()


def create_artifact_for_content(
        *,
        user_id: int,
        artifact_type: str,
        title: str,
        mode: str,
        source_chat_id: int,
        fragments=None,
) -> Artifact:
    try:
        artifact = artifact_repository.create(
            user_id=user_id,
            type=artifact_type,
            title=title,
            status=Artifact.Status.FINAL,
            mode=mode,
            source_chat_id=source_chat_id,
            fragments=fragments,
        )
        return artifact
    except Exception:
        logger.error(
            "Failed to create artifact header for content generation",
            extra={"user_id": user_id, "artifact_type": artifact_type, "source_chat_id": source_chat_id},
            exc_info=True,
        )
        raise ArtifactCreationFailedException()


@transaction.atomic
def clear_chat_artifacts(chat_id: int, deleted_by: int) -> None:
    from apps.artifact_message.models import ArtifactMessage
    from apps.artifact_report.models import ArtifactReport
    from apps.artifact_checklist.models import ArtifactChecklist
    from apps.artifact_quiz.models import ArtifactQuiz
    from apps.artifact_timeline.models import ArtifactTimeline
    from apps.artifact_lessons_learned.models import ArtifactLessonsLearned
    from apps.artifact_decision_brief.models import ArtifactDecisionBrief

    for content_model in (
            ArtifactMessage,
            ArtifactReport,
            ArtifactChecklist,
            ArtifactQuiz,
            ArtifactTimeline,
            ArtifactLessonsLearned,
            ArtifactDecisionBrief,
    ):
        content_model.objects.filter(artifact__source_chat_id=chat_id).delete(deleted_by=deleted_by)

    artifact_ids = list(Artifact.objects.filter(source_chat_id=chat_id).values_list("id", flat=True))
    if artifact_ids:
        ArtifactPin.objects.filter(artifact_id__in=artifact_ids).delete()
        ArtifactBookmark.objects.filter(artifact_id__in=artifact_ids).delete()
        ArtifactFeedback.objects.filter(artifact_id__in=artifact_ids).delete()
        ArtifactThreadReply.objects.filter(parent_artifact_id__in=artifact_ids).delete()

    Artifact.objects.filter(source_chat_id=chat_id).delete(deleted_by=deleted_by)
