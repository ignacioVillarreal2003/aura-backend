from django.db.models import QuerySet

from apps.artifact.models.artifact_thread_reply import ArtifactThreadReply


class ThreadRepository:
    @staticmethod
    def get_by_artifact(parent_artifact_id: int) -> QuerySet[ArtifactThreadReply]:
        return ArtifactThreadReply.objects.filter(parent_artifact_id=parent_artifact_id).order_by("-created_at")

    @staticmethod
    def create(parent_artifact_id: int, message: str, created_by: int) -> ArtifactThreadReply:
        return ArtifactThreadReply.objects.create(
            parent_artifact_id=parent_artifact_id,
            message=message,
            created_by=created_by,
        )

    @staticmethod
    def get_by_id(reply_id: int) -> ArtifactThreadReply | None:
        return ArtifactThreadReply.objects.filter(id=reply_id).first()

    @staticmethod
    def update(reply: ArtifactThreadReply, message: str, updated_by: int) -> ArtifactThreadReply:
        reply.message = message
        reply.updated_by = updated_by
        reply.save(update_fields=["message", "updated_by"])
        return reply

    @staticmethod
    def soft_delete(reply: ArtifactThreadReply, deleted_by: int) -> None:
        reply.delete(deleted_by=deleted_by)


thread_repository = ThreadRepository()
