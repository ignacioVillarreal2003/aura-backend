import logging
from datetime import datetime
from typing import Optional
from django.db import transaction

from apps.artifact.models import Artifact

logger = logging.getLogger(__name__)


class ArtifactRepository:
    def create(
            self,
            *,
            user_id: int,
            type: str,
            source_chat_id: int,
            mode: str = Artifact.Mode.DIRECT,
            fragments=None,
    ) -> Artifact:
        return Artifact.objects.create(
            created_by=user_id,
            type=type,
            mode=mode,
            fragments=fragments,
            source_chat_id=source_chat_id,
        )

    def get_by_id(self, artifact_id: int) -> Optional[Artifact]:
        return Artifact.objects.filter(id=artifact_id).first()

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
        return qs

    def list_by_chat(self, source_chat_id: int, artifact_type: Optional[str] = None):
        qs = Artifact.objects.filter(source_chat_id=source_chat_id)
        if artifact_type:
            qs = qs.filter(type=artifact_type)
        return qs.order_by("-created_at")

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
        return qs.order_by("-created_at")

    def list_all(self, artifact_type: Optional[str] = None):
        qs = Artifact.objects.all()
        if artifact_type:
            qs = qs.filter(type=artifact_type)
        return qs

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
        return qs.order_by("-created_at")

    def touch(self, artifact: Artifact, *, updated_by: int) -> Artifact:
        artifact.updated_by = updated_by
        artifact.save(update_fields=["updated_by", "updated_at"])
        return artifact

    def soft_delete(self, artifact: Artifact, deleted_by: int) -> None:
        artifact.delete(deleted_by=deleted_by)


artifact_repository = ArtifactRepository()
