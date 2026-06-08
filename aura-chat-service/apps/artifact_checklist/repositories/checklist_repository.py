import logging
from typing import Optional
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.query import Prefetch

from apps.artifact_checklist.models import ArtifactChecklist, ArtifactChecklistItem, ArtifactChecklistSection

logger = logging.getLogger(__name__)

_SECTIONS_PREFETCH = Prefetch("sections", queryset=ArtifactChecklistSection.objects.prefetch_related(
    Prefetch("items", queryset=ArtifactChecklistItem.objects.order_by("position"))
).order_by("position"))


def _with_prefetch(qs):
    return qs.select_related("artifact").prefetch_related(_SECTIONS_PREFETCH)


def _with_counts(qs):
    return qs.select_related("artifact").annotate(
        item_count=Count("sections__items", distinct=True),
        checked_count=Count(
            "sections__items",
            filter=Q(sections__items__is_checked=True),
            distinct=True,
        ),
    )


def _bulk_create_sections(checklist_id: int, sections: list) -> None:
    section_objs = [
        ArtifactChecklistSection(checklist_id=checklist_id, title=sec["title"], position=sec["position"])
        for sec in sections
    ]
    created = ArtifactChecklistSection.objects.bulk_create(section_objs)

    item_objs = []
    for section_obj, section_data in zip(created, sections):
        for item in section_data.get("items", []):
            item_objs.append(ArtifactChecklistItem(
                section_id=section_obj.id,
                text=item["text"],
                is_checked=bool(item.get("is_checked", False)),
                notes=str(item.get("notes", "")),
                position=item["position"],
            ))
    if item_objs:
        ArtifactChecklistItem.objects.bulk_create(item_objs)


class ChecklistRepository:
    def create(
            self,
            *,
            user_id: int,
            sections: list,
            artifact_id: int,
    ) -> ArtifactChecklist:
        checklist = ArtifactChecklist.objects.create(
            created_by=user_id,
            artifact_id=artifact_id,
        )
        _bulk_create_sections(checklist.id, sections)
        return _with_prefetch(ArtifactChecklist.objects.filter(id=checklist.id)).first()

    def get_by_id(self, checklist_id: int) -> Optional[ArtifactChecklist]:
        return _with_prefetch(ArtifactChecklist.objects.filter(id=checklist_id)).first()

    def get_by_id_for_update(self, checklist_id: int) -> Optional[ArtifactChecklist]:
        return ArtifactChecklist.objects.select_for_update().select_related("artifact").filter(id=checklist_id).first()

    def list_by_user(self, user_id: int):
        return _with_counts(ArtifactChecklist.objects.filter(created_by=user_id))

    def list_by_chat(self, source_chat_id: int):
        return _with_counts(ArtifactChecklist.objects.filter(artifact__source_chat_id=source_chat_id))

    def list_all(self):
        return _with_counts(ArtifactChecklist.objects.all())

    @transaction.atomic
    def update(
            self,
            checklist: ArtifactChecklist,
            *,
            updated_by: int,
            sections: Optional[list] = None,
    ) -> ArtifactChecklist:
        if sections is not None:
            ArtifactChecklistSection.objects.filter(checklist_id=checklist.id).delete()
            _bulk_create_sections(checklist.id, sections)
            checklist.updated_by = updated_by
            checklist.save(update_fields=["updated_by"])
        return _with_prefetch(ArtifactChecklist.objects.filter(id=checklist.id)).first()

    def soft_delete(self, checklist: ArtifactChecklist, deleted_by: int) -> None:
        checklist.delete(deleted_by=deleted_by)


checklist_repository = ChecklistRepository()
