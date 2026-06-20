import logging
from django.db import transaction
from django.db.models import Count, Exists, F, FilteredRelation, IntegerField, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce

from apps.artifact.models.artifact import Artifact
from apps.artifact_message.models import ArtifactMessage

logger = logging.getLogger(__name__)


class MessageRepository:
    @staticmethod
    @transaction.atomic
    def create(
            chat_id: int,
            message: str,
            sender_type: str,
            created_by: int,
            fragments: list | None = None,
    ) -> ArtifactMessage:
        artifact = Artifact.objects.create(
            source_chat_id=chat_id,
            type=Artifact.Type.MESSAGE,
            fragments=fragments or None,
            created_by=created_by,
        )
        return ArtifactMessage.objects.create(
            artifact=artifact,
            message=message,
            sender_type=sender_type,
            created_by=created_by,
        )

    @staticmethod
    def get_messages_by_chat(chat_id: int, user_id: int | None = None) -> QuerySet[ArtifactMessage]:
        from apps.artifact.models.artifact_bookmark import ArtifactBookmark
        from apps.artifact.models.artifact_thread_reply import ArtifactThreadReply

        qs = ArtifactMessage.objects.filter(
            artifact__source_chat_id=chat_id,
            artifact__type=Artifact.Type.MESSAGE,
        ).select_related("artifact")

        if user_id is not None:
            qs = qs.annotate(
                my_feedback=FilteredRelation(
                    "artifact__feedback",
                    condition=Q(artifact__feedback__created_by=user_id),
                )
            ).annotate(
                is_bookmarked=Exists(
                    ArtifactBookmark.objects.filter(
                        artifact_id=OuterRef("artifact_id"),
                        created_by=user_id,
                    )
                ),
                user_feedback=F("my_feedback__value"),
                user_feedback_reason=F("my_feedback__reason"),
                user_feedback_comment=F("my_feedback__comment"),
                thread_reply_count=Coalesce(
                    Subquery(
                        ArtifactThreadReply.objects.filter(parent_artifact_id=OuterRef("artifact_id"))
                        .values("parent_artifact_id")
                        .annotate(c=Count("id"))
                        .values("c")[:1],
                        output_field=IntegerField(),
                    ),
                    0,
                ),
            )

        return qs

    @staticmethod
    def get_recent_messages(chat_id: int, limit: int = 10) -> list[ArtifactMessage]:
        return list(
            ArtifactMessage.objects
            .filter(artifact__source_chat_id=chat_id, artifact__type=Artifact.Type.MESSAGE)
            .select_related("artifact")
            .order_by("-created_at", "-id")[:limit]
        )

    @staticmethod
    def get_last_ai_message(chat_id: int) -> ArtifactMessage | None:
        return (
            ArtifactMessage.objects
            .filter(
                artifact__source_chat_id=chat_id,
                artifact__type=Artifact.Type.MESSAGE,
                sender_type=ArtifactMessage.SenderType.ASSISTANT,
            )
            .select_related("artifact")
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def get_by_id(message_id: int) -> ArtifactMessage | None:
        return (
            ArtifactMessage.objects
            .filter(pk=message_id, artifact__type=Artifact.Type.MESSAGE)
            .select_related("artifact")
            .first()
        )

    @staticmethod
    def get_by_id_and_chat(message_id: int, chat_id: int) -> ArtifactMessage | None:
        return (
            ArtifactMessage.objects
            .filter(
                pk=message_id,
                artifact__source_chat_id=chat_id,
                artifact__type=Artifact.Type.MESSAGE,
            )
            .select_related("artifact")
            .first()
        )

    @staticmethod
    def soft_delete_by_chat(chat_id: int, deleted_by: int) -> None:
        ArtifactMessage.objects.filter(
            artifact__source_chat_id=chat_id,
            artifact__type=Artifact.Type.MESSAGE,
        ).delete(deleted_by=deleted_by)


message_repository = MessageRepository()
