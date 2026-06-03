from apps.message.models.message_bookmark import ArtifactBookmark


class BookmarkRepository:
    @staticmethod
    def create(artifact_id: int, user_id: int) -> ArtifactBookmark:
        obj, _ = ArtifactBookmark.objects.get_or_create(artifact_id=artifact_id, user_id=user_id)
        return obj

    @staticmethod
    def delete(artifact_id: int, user_id: int) -> bool:
        deleted, _ = ArtifactBookmark.objects.filter(
            artifact_id=artifact_id, user_id=user_id
        ).delete()
        return deleted > 0

    @staticmethod
    def get_bookmarked_artifact_ids(chat_id: int, user_id: int) -> list[int]:
        from apps.artifact.models.artifact import Artifact

        return list(
            ArtifactBookmark.objects.filter(
                user_id=user_id,
                artifact__source_chat_id=chat_id,
            ).values_list("artifact_id", flat=True)
        )


bookmark_repository = BookmarkRepository()
