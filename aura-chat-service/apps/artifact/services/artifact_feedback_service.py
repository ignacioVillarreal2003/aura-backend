from apps.artifact.models.artifact import Artifact
from apps.artifact_message.models import ArtifactMessage
from apps.artifact.models.artifact_feedback import ArtifactFeedback
from apps.artifact.repositories.artifact_feedback_repository import feedback_repository
from apps.artifact.services.artifact_access import require_interaction_access
from apps.artifact_message.exceptions import NotAIMessageException
from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization import AccessControl
from core.authorization.permissions import SET_MESSAGE_FEEDBACK


def _require_ai_artifact(user_id: int, artifact_id: int) -> Artifact:
    artifact = require_interaction_access(user_id, artifact_id)
    if artifact.type == Artifact.Type.MESSAGE:
        try:
            msg_content = artifact.message_content
        except ArtifactMessage.DoesNotExist:
            raise NotAIMessageException()
        if msg_content.sender_type != ArtifactMessage.SenderType.ASSISTANT:
            raise NotAIMessageException()
    return artifact


class FeedbackService:
    def set_feedback(
            self,
            user: AuthenticatedUser,
            artifact_id: int,
            value: int,
            reason: str | None = None,
            comment: str | None = None,
    ) -> ArtifactFeedback:
        AccessControl.require_permissions(user, frozenset({SET_MESSAGE_FEEDBACK}))
        _require_ai_artifact(user.id, artifact_id)
        fb = feedback_repository.set(
            artifact_id=artifact_id,
            created_by=user.id,
            value=value,
            reason=reason,
            comment=comment,
        )
        if value == -1:
            from apps.artifact.services.feedback_evaluation_service import feedback_evaluation_service
            feedback_evaluation_service.trigger_evaluation(fb.id)
        return fb


    def delete_feedback(self, user: AuthenticatedUser, artifact_id: int) -> None:
        AccessControl.require_permissions(user, frozenset({SET_MESSAGE_FEEDBACK}))
        _require_ai_artifact(user.id, artifact_id)
        feedback_repository.delete(artifact_id=artifact_id, created_by=user.id)


feedback_service = FeedbackService()
