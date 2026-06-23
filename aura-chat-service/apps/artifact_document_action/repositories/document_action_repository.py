import logging
from typing import Optional

from apps.artifact_document_action.models import ArtifactDocumentAction

logger = logging.getLogger(__name__)


def _with_related(qs):
    return qs.select_related("artifact")


class DocumentActionRepository:
    def create(
            self,
            *,
            user_id: int,
            instruction: str,
            action: Optional[str],
            result: str,
            artifact_id: int,
            title: str = "",
            description: str = "",
    ) -> ArtifactDocumentAction:
        obj = ArtifactDocumentAction.objects.create(
            created_by=user_id,
            instruction=instruction,
            action=action,
            result=result,
            artifact_id=artifact_id,
            title=title,
            description=description,
        )
        return _with_related(ArtifactDocumentAction.objects.filter(id=obj.id)).first()

    def get_by_id(self, document_action_id: int) -> Optional[ArtifactDocumentAction]:
        return _with_related(ArtifactDocumentAction.objects.filter(id=document_action_id)).first()

    def get_by_id_for_update(self, document_action_id: int) -> Optional[ArtifactDocumentAction]:
        return (
            ArtifactDocumentAction.objects
            .select_for_update()
            .select_related("artifact")
            .filter(id=document_action_id)
            .first()
        )

    def list_by_chat(self, source_chat_id: int):
        return _with_related(ArtifactDocumentAction.objects.filter(artifact__source_chat_id=source_chat_id))

    def list_all(self):
        return _with_related(ArtifactDocumentAction.objects.all())

    def soft_delete(self, obj: ArtifactDocumentAction, deleted_by: int) -> None:
        obj.delete(deleted_by=deleted_by)


document_action_repository = DocumentActionRepository()
