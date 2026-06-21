import logging
from datetime import datetime
from typing import Optional
from django.db import transaction

from apps.artifact.models import Artifact

logger = logging.getLogger(__name__)

# One-to-one type content relations the artifact list/summary serializers read
# (title, linked_id, message preview). Joining them up front turns the per-row
# "_content" lookups into a single query instead of an N+1 over the result set.
_CONTENT_RELATIONS = (
    "report_content",
    "checklist_content",
    "quiz_content",
    "timeline_content",
    "lessons_learned_content",
    "decision_brief_content",
    "document_summary_content",
    "document_action_content",
    "message_content",
)


def _with_content(qs):
    return qs.select_related(*_CONTENT_RELATIONS)


class ArtifactRepository:
    def create(
            self,
            *,
            user_id: int,
            type: str,
            source_chat_id: int,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
            fragments=None,
    ) -> Artifact:
        return Artifact.objects.create(
            created_by=user_id,
            type=type,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
            document_ids=document_ids or [],
            fragments=fragments,
            source_chat_id=source_chat_id,
        )

    def get_by_id(self, artifact_id: int) -> Optional[Artifact]:
        return _with_content(Artifact.objects.filter(id=artifact_id)).first()

    def get_by_id_for_update(self, artifact_id: int) -> Optional[Artifact]:
        return Artifact.objects.select_for_update().filter(id=artifact_id).first()

    def list_by_user(
            self,
            user_id: int,
            artifact_type: Optional[str] = None,
            source_chat_id: Optional[int] = None,
    ):
        qs = Artifact.objects.filter(created_by=user_id)
        if artifact_type:
            qs = qs.filter(type=artifact_type)
        if source_chat_id is not None:
            qs = qs.filter(source_chat_id=source_chat_id)
        return _with_content(qs)

    def list_by_chat(self, source_chat_id: int, artifact_type: Optional[str] = None):
        qs = Artifact.objects.filter(source_chat_id=source_chat_id)
        if artifact_type:
            qs = qs.filter(type=artifact_type)
        return _with_content(qs).order_by("-created_at")

    def list_by_chat_filtered(
            self,
            source_chat_id: int,
            artifact_type: Optional[str] = None,
            created_by: Optional[int] = None,
            date_from: Optional[datetime] = None,
            date_to: Optional[datetime] = None,
    ):
        qs = Artifact.objects.filter(source_chat_id=source_chat_id)
        if artifact_type:
            qs = qs.filter(type=artifact_type)
        if created_by is not None:
            qs = qs.filter(created_by=created_by)
        if date_from is not None:
            qs = qs.filter(created_at__gte=date_from)
        if date_to is not None:
            qs = qs.filter(created_at__lte=date_to)
        return _with_content(qs).order_by("-created_at")

    def list_all(self, artifact_type: Optional[str] = None):
        qs = Artifact.objects.all()
        if artifact_type:
            qs = qs.filter(type=artifact_type)
        return _with_content(qs)

    def list_all_for_chat_filtered(
            self,
            source_chat_id: int,
            artifact_type: Optional[str] = None,
            created_by: Optional[int] = None,
            date_from: Optional[datetime] = None,
            date_to: Optional[datetime] = None,
    ):
        qs = Artifact.objects.filter(source_chat_id=source_chat_id)
        if artifact_type:
            qs = qs.filter(type=artifact_type)
        if created_by is not None:
            qs = qs.filter(created_by=created_by)
        if date_from is not None:
            qs = qs.filter(created_at__gte=date_from)
        if date_to is not None:
            qs = qs.filter(created_at__lte=date_to)
        return _with_content(qs).order_by("-created_at")

    def touch(self, artifact: Artifact, *, updated_by: int) -> Artifact:
        artifact.updated_by = updated_by
        artifact.save(update_fields=["updated_by", "updated_at"])
        return artifact

    def soft_delete(self, artifact: Artifact, deleted_by: int) -> None:
        artifact.delete(deleted_by=deleted_by)


artifact_repository = ArtifactRepository()
