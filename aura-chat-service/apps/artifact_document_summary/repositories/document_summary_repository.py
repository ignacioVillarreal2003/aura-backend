import logging
from typing import Optional

from apps.artifact_document_summary.models import ArtifactDocumentSummary

logger = logging.getLogger(__name__)


def _with_related(qs):
    return qs.select_related("artifact")


class DocumentSummaryRepository:
    def create(
            self,
            *,
            user_id: int,
            summary: str,
            artifact_id: int,
            title: str = "",
            description: str = "",
    ) -> ArtifactDocumentSummary:
        obj = ArtifactDocumentSummary.objects.create(
            created_by=user_id,
            summary=summary,
            artifact_id=artifact_id,
            title=title,
            description=description,
        )
        return _with_related(ArtifactDocumentSummary.objects.filter(id=obj.id)).first()

    def get_by_id(self, document_summary_id: int) -> Optional[ArtifactDocumentSummary]:
        return _with_related(ArtifactDocumentSummary.objects.filter(id=document_summary_id)).first()

    def get_by_id_for_update(self, document_summary_id: int) -> Optional[ArtifactDocumentSummary]:
        return (
            ArtifactDocumentSummary.objects
            .select_for_update()
            .select_related("artifact")
            .filter(id=document_summary_id)
            .first()
        )

    def list_by_chat(self, source_chat_id: int):
        return _with_related(ArtifactDocumentSummary.objects.filter(artifact__source_chat_id=source_chat_id))

    def list_all(self):
        return _with_related(ArtifactDocumentSummary.objects.all())

    def soft_delete(self, obj: ArtifactDocumentSummary, deleted_by: int) -> None:
        obj.delete(deleted_by=deleted_by)


document_summary_repository = DocumentSummaryRepository()
