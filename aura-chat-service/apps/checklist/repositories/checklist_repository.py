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
    ) -> Checklist:
        return Checklist.objects.create(
            created_by=user_id,
            title=title,
            items=items,
            mode=mode,
            metadata=metadata,
        )

    def get_by_id(self, checklist_id: int) -> Optional[Checklist]:
        return Checklist.objects.filter(id=checklist_id, deleted_at__isnull=True).first()

    def list_by_user(self, user_id: int):
        return Checklist.objects.filter(created_by=user_id, deleted_at__isnull=True)

    def update(
            self,
            checklist: Checklist,
            *,
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
            checklist.save(update_fields=update_fields)
        return checklist

    def soft_delete(self, checklist: Checklist, deleted_by: int) -> None:
        checklist.delete(deleted_by=deleted_by)


checklist_repository = ChecklistRepository()
