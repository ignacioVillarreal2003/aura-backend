import logging
from typing import Optional
from django.db import transaction

from apps.artifact.models import Artifact
from apps.artifact.repositories.artifact_version_repository import artifact_version_repository

logger = logging.getLogger(__name__)


class ArtifactRepository:
    @transaction.atomic
    def create(
        self,
        *,
        user_id: int,
        type: str,
        source_chat_id: int,
        title: str = "",
        description: str = "",
        status: str = Artifact.Status.DRAFT,
        version: int = 1,
        mode: str = Artifact.Mode.DIRECT,
        fragments=None,
    ) -> Artifact:
        artifact = Artifact.objects.create(
            created_by=user_id,
            type=type,
            title=title,
            description=description,
            status=status,
            version=version,
            mode=mode,
            fragments=fragments,
            source_chat_id=source_chat_id,
        )
        artifact_version_repository.add_version(
            artifact=artifact, created_by=user_id, change_summary="Versión inicial"
        )
        return artifact

    def get_by_id(self, artifact_id: int) -> Optional[Artifact]:
        return Artifact.objects.filter(id=artifact_id).first()

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
        return qs.order_by("created_at")

    def list_all(self, artifact_type: Optional[str] = None):
        qs = Artifact.objects.all()
        if artifact_type:
            qs = qs.filter(type=artifact_type)
        return qs

    @transaction.atomic
    def update(
        self,
        artifact: Artifact,
        *,
        updated_by: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        change_summary: str = "",
    ) -> Artifact:
        update_fields: list[str] = []
        if title is not None:
            artifact.title = title
            update_fields.append("title")
        if description is not None:
            artifact.description = description
            update_fields.append("description")
        if status is not None:
            artifact.status = status
            update_fields.append("status")

        if not update_fields:
            return artifact

        artifact.version = (artifact.version or 1) + 1
        artifact.updated_by = updated_by
        update_fields.extend(["version", "updated_by"])
        artifact.save(update_fields=update_fields)
        artifact_version_repository.add_version(
            artifact=artifact, created_by=updated_by, change_summary=change_summary
        )
        return artifact

    def soft_delete(self, artifact: Artifact, deleted_by: int) -> None:
        artifact.delete(deleted_by=deleted_by)


artifact_repository = ArtifactRepository()
