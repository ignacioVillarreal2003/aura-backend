import logging
from typing import Optional
from django.db.models import Count, Q
from django.db.models.query import Prefetch

from apps.checklist.models import Checklist, ChecklistItem, ChecklistSection

logger = logging.getLogger(__name__)

_SECTIONS_PREFETCH = Prefetch("sections", queryset=ChecklistSection.objects.prefetch_related(
    Prefetch("items", queryset=ChecklistItem.objects.order_by("position"))
).order_by("position"))


def _with_prefetch(qs):
    return qs.prefetch_related(_SECTIONS_PREFETCH)


def _with_counts(qs):
    return qs.annotate(
        item_count=Count("sections__items", distinct=True),
        checked_count=Count(
            "sections__items",
            filter=Q(sections__items__is_checked=True),
            distinct=True,
        ),
    )


def _bulk_create_sections(checklist_id: int, sections: list) -> None:
    section_objs = [
        ChecklistSection(checklist_id=checklist_id, title=sec["title"], position=sec["position"])
        for sec in sections
    ]
    created = ChecklistSection.objects.bulk_create(section_objs)

    item_objs = []
    for section_obj, section_data in zip(created, sections):
        for item in section_data.get("items", []):
            item_objs.append(ChecklistItem(
                section_id=section_obj.id,
                text=item["text"],
                is_checked=bool(item.get("is_checked", False)),
                notes=str(item.get("notes", "")),
                position=item["position"],
            ))
    if item_objs:
        ChecklistItem.objects.bulk_create(item_objs)


class ChecklistRepository:
    def create(
            self,
            *,
            user_id: int,
            title: str,
            sections: list,
            mode: str,
            source_chat_id: Optional[int] = None,
            artifact_id: Optional[int] = None,
    ) -> Checklist:
        checklist = Checklist.objects.create(
            created_by=user_id,
            title=title,
            mode=mode,
            source_chat_id=source_chat_id,
            artifact_id=artifact_id,
        )
        _bulk_create_sections(checklist.id, sections)
        return _with_prefetch(Checklist.objects.filter(id=checklist.id)).first()

    def get_by_id(self, checklist_id: int) -> Optional[Checklist]:
        return _with_prefetch(Checklist.objects.filter(id=checklist_id)).first()

    def list_by_user(self, user_id: int):
        return _with_counts(Checklist.objects.filter(created_by=user_id))

    def list_by_chat(self, source_chat_id: int):
        return _with_counts(Checklist.objects.filter(source_chat_id=source_chat_id))

    def list_all(self):
        return _with_counts(Checklist.objects.all())

    def update(
            self,
            checklist: Checklist,
            *,
            updated_by: int,
            title: Optional[str] = None,
            sections: Optional[list] = None,
    ) -> Checklist:
        update_fields = []
        if title is not None:
            checklist.title = title
            update_fields.append("title")
        if sections is not None:
            ChecklistSection.objects.filter(checklist_id=checklist.id).delete()
            _bulk_create_sections(checklist.id, sections)
        if update_fields:
            checklist.updated_by = updated_by
            update_fields.append("updated_by")
            checklist.save(update_fields=update_fields)
        elif sections is not None:
            checklist.updated_by = updated_by
            checklist.save(update_fields=["updated_by"])
        return _with_prefetch(Checklist.objects.filter(id=checklist.id)).first()

    def soft_delete(self, checklist: Checklist, deleted_by: int) -> None:
        checklist.delete(deleted_by=deleted_by)


checklist_repository = ChecklistRepository()
