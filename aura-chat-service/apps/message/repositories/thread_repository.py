from django.db.models import QuerySet

from apps.message.models.message_thread_reply import ArtifactThreadReply


class ThreadRepository:
    @staticmethod
    def get_by_artifact(parent_artifact_id: int) -> QuerySet[ArtifactThreadReply]:
        return ArtifactThreadReply.objects.filter(parent_artifact_id=parent_artifact_id)

    @staticmethod
    def create(parent_artifact_id: int, message: str, created_by: int) -> ArtifactThreadReply:
        return ArtifactThreadReply.objects.create(
            parent_artifact_id=parent_artifact_id,
            message=message,
            created_by=created_by,
        )


thread_repository = ThreadRepository()
