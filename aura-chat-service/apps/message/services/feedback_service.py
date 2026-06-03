from apps.artifact.models.artifact import Artifact
from apps.artifact.repositories.artifact_repository import artifact_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import (
    MessageAccessDeniedException,
    MessageNotFoundException,
    NotAIMessageException,
)
from apps.message.models.message_feedback import ArtifactFeedback
from apps.message.repositories.feedback_repository import feedback_repository
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import SET_MESSAGE_FEEDBACK


def _require_ai_artifact(user_id: int, chat_id: int, artifact_id: int) -> Artifact:
    if not membership_repository.is_active_member(chat_id, user_id):
        raise MessageAccessDeniedException()
    artifact = artifact_repository.get_by_id(artifact_id)
    if artifact is None or artifact.source_chat_id != chat_id:
        raise MessageNotFoundException()
    msg_content = getattr(artifact, "_message_content_cache", None)
    if msg_content is None:
        try:
            msg_content = artifact.message_content
        except Exception:
            raise MessageNotFoundException()
    from apps.artifact.models.artifact_message import ArtifactMessage
    if msg_content.sender_type not in (ArtifactMessage.SenderType.SYSTEM, ArtifactMessage.SenderType.ASSISTANT):
        raise NotAIMessageException()
    return artifact


class FeedbackService:
    def set_feedback(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            artifact_id: int,
            value: int,
            reason: str | None = None,
            comment: str | None = None,
    ) -> ArtifactFeedback:
        AccessControl.require_permissions(user, frozenset({SET_MESSAGE_FEEDBACK}))
        _require_ai_artifact(user.id, chat_id, artifact_id)
        return feedback_repository.set(
            artifact_id=artifact_id,
            user_id=user.id,
            value=value,
            reason=reason,
            comment=comment,
        )

    def delete_feedback(
            self, user: AuthenticatedUser, chat_id: int, artifact_id: int
    ) -> None:
        AccessControl.require_permissions(user, frozenset({SET_MESSAGE_FEEDBACK}))
        _require_ai_artifact(user.id, chat_id, artifact_id)
        feedback_repository.delete(artifact_id=artifact_id, user_id=user.id)


feedback_service = FeedbackService()
