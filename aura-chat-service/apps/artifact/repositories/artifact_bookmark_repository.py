from django.db.models import QuerySet

from apps.artifact.models.artifact import Artifact
from apps.artifact.models.artifact_bookmark import ArtifactBookmark


class BookmarkRepository:
    @staticmethod
    def create(artifact_id: int, user_id: int) -> ArtifactBookmark:
        obj, _ = ArtifactBookmark.objects.get_or_create(artifact_id=artifact_id, created_by=user_id)
        return obj

    @staticmethod
    def delete(artifact_id: int, user_id: int) -> bool:
        deleted, _ = ArtifactBookmark.objects.filter(
            artifact_id=artifact_id, created_by=user_id
        ).delete()
        return deleted > 0

    @staticmethod
    def list_bookmarked_artifacts(chat_id: int, user_id: int) -> QuerySet[Artifact]:
        return (
            Artifact.objects.filter(source_chat_id=chat_id, bookmarks__created_by=user_id)
            .select_related("message_content")
            .order_by("-created_at")
        )


bookmark_repository = BookmarkRepository()
