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
        obj, created = ArtifactFeedback.objects.update_or_create(
            artifact_id=artifact_id,
            user_id=user_id,
            defaults={
                "value": value,
                "reason": reason,
                "comment": comment,
                "updated_at": timezone.now(),
            },
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
