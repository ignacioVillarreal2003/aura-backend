import logging
from typing import Optional

from apps.checklist.models import Checklist

logger = logging.getLogger(__name__)


class ChecklistRepository:
    def create(
            self,
            *,
            user_id: int,
            title: str,
            items: list,
            mode: str,
            metadata: dict,
            source_chat_id: Optional[int] = None,
    ) -> Checklist:
        return Checklist.objects.create(
            created_by=user_id,
            title=title,
            items=items,
            mode=mode,
            metadata=metadata,
            source_chat_id=source_chat_id,
        )

    def get_by_id(self, checklist_id: int) -> Optional[Checklist]:
        return Checklist.objects.filter(id=checklist_id).first()

    def list_by_user(self, user_id: int, source_chat_id: Optional[int] = None):
        qs = Checklist.objects.filter(created_by=user_id)
        if source_chat_id is not None:
            qs = qs.filter(source_chat_id=source_chat_id)
        return qs

    def list_by_chat(self, source_chat_id: int):
        return Checklist.objects.filter(source_chat_id=source_chat_id)

    def list_all(self):
        return Checklist.objects.all()

    def update(
            self,
            checklist: Checklist,
            *,
            updated_by: int,
            title: Optional[str] = None,
            items: Optional[list] = None,
    ) -> Checklist:
        update_fields = []
        if title is not None:
            checklist.title = title
            update_fields.append("title")
        if items is not None:
            checklist.items = items
            update_fields.append("items")
        if update_fields:
            checklist.updated_by = updated_by
            update_fields.append("updated_by")
            checklist.save(update_fields=update_fields)
        return checklist

    def soft_delete(self, checklist: Checklist, deleted_by: int) -> None:
        checklist.delete(deleted_by=deleted_by)


checklist_repository = ChecklistRepository()
