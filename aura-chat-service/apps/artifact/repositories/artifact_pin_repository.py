from django.db.models import QuerySet

from apps.artifact.models.artifact_pin import ArtifactPin


class PinRepository:
    @staticmethod
    def pin(artifact_id: int, chat_id: int, pinned_by: int) -> tuple[ArtifactPin, bool]:
        return ArtifactPin.objects.get_or_create(
            artifact_id=artifact_id,
            chat_id=chat_id,
            defaults={"pinned_by": pinned_by},
        )

    @staticmethod
    def unpin(artifact_id: int, chat_id: int) -> bool:
        deleted, _ = ArtifactPin.objects.filter(
            artifact_id=artifact_id,
            chat_id=chat_id,
        ).delete()
        return deleted > 0

    @staticmethod
    def list_by_chat(chat_id: int) -> QuerySet[ArtifactPin]:
        return (
            ArtifactPin.objects.filter(chat_id=chat_id, artifact__deleted_at__isnull=True)
            .select_related("artifact", "artifact__message_content")
            .order_by("pinned_at")
        )

    @staticmethod
    def exists(artifact_id: int, chat_id: int) -> bool:
        return ArtifactPin.objects.filter(
            artifact_id=artifact_id,
            chat_id=chat_id,
        ).exists()


pin_repository = PinRepository()
