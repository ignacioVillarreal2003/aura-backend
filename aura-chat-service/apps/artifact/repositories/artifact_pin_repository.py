from django.db.models import QuerySet

from apps.artifact.models.artifact_pin import ArtifactPin
from apps.artifact.repositories.artifact_repository import _CONTENT_RELATIONS


class PinRepository:
    @staticmethod
    def pin(artifact_id: int, created_by: int) -> tuple[ArtifactPin, bool]:
        return ArtifactPin.objects.get_or_create(
            artifact_id=artifact_id,
            defaults={"created_by": created_by},
        )

    @staticmethod
    def unpin(artifact_id: int) -> bool:
        deleted, _ = ArtifactPin.objects.filter(artifact_id=artifact_id).delete()
        return deleted > 0

    @staticmethod
    def list_by_chat(chat_id: int) -> QuerySet[ArtifactPin]:
        return (
            ArtifactPin.objects.filter(
                artifact__source_chat_id=chat_id,
                artifact__deleted_at__isnull=True,
            )
            .select_related(
                "artifact",
                *(f"artifact__{rel}" for rel in _CONTENT_RELATIONS),
            )
            .order_by("created_at")
        )

    @staticmethod
    def exists(artifact_id: int) -> bool:
        return ArtifactPin.objects.filter(artifact_id=artifact_id).exists()


pin_repository = PinRepository()
