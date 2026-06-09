from django.utils import timezone

from apps.artifact.models.artifact_feedback import ArtifactFeedback


class FeedbackRepository:
    @staticmethod
    def set(
            artifact_id: int,
            user_id: int,
            value: int,
            reason: str | None = None,
            comment: str | None = None,
    ) -> ArtifactFeedback:
        try:
            obj = ArtifactFeedback.objects.get(artifact_id=artifact_id, user_id=user_id)
            obj.value = value
            obj.reason = reason
            obj.comment = comment
            obj.updated_by = user_id
            obj.updated_at = timezone.now()
            obj.save(update_fields=["value", "reason", "comment", "updated_by", "updated_at"])
        except ArtifactFeedback.DoesNotExist:
            obj = ArtifactFeedback.objects.create(
                artifact_id=artifact_id,
                user_id=user_id,
                value=value,
                reason=reason,
                comment=comment,
                created_by=user_id,
            )
        return obj

    @staticmethod
    def delete(artifact_id: int, user_id: int) -> bool:
        deleted, _ = ArtifactFeedback.objects.filter(
            artifact_id=artifact_id, user_id=user_id
        ).delete()
        return deleted > 0

    @staticmethod
    def get(artifact_id: int, user_id: int) -> ArtifactFeedback | None:
        return ArtifactFeedback.objects.filter(artifact_id=artifact_id, user_id=user_id).first()


feedback_repository = FeedbackRepository()
