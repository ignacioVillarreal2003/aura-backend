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
            document_ids: list,
            instruction: str,
            action: Optional[str],
            result: str,
            artifact_id: int,
    ) -> ArtifactDocumentAction:
        obj = ArtifactDocumentAction.objects.create(
            created_by=user_id,
            document_ids=document_ids,
            instruction=instruction,
            action=action,
            result=result,
            artifact_id=artifact_id,
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

    def update(
            self,
            obj: ArtifactDocumentAction,
            *,
            updated_by: int,
            result: Optional[str] = None,
            instruction: Optional[str] = None,
    ) -> ArtifactDocumentAction:
        update_fields = []
        for field_name, value in (("result", result), ("instruction", instruction)):
            if value is not None:
                setattr(obj, field_name, value)
                update_fields.append(field_name)
        if update_fields:
            obj.updated_by = updated_by
            update_fields.append("updated_by")
            obj.save(update_fields=update_fields)
        return _with_related(ArtifactDocumentAction.objects.filter(id=obj.id)).first()

    def soft_delete(self, obj: ArtifactDocumentAction, deleted_by: int) -> None:
        obj.delete(deleted_by=deleted_by)


document_action_repository = DocumentActionRepository()
