import logging
from typing import Optional
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


def _bulk_create_sections(checklist_id: int, sections: list, created_by: int) -> None:
    section_objs = [
        ArtifactChecklistSection(checklist_id=checklist_id, title=sec["title"], position=sec["position"], created_by=created_by)
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
                position=item["position"],
                created_by=created_by,
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
            title: str = "",
            description: str = "",
            query: str = "",
    ) -> ArtifactChecklist:
        checklist = ArtifactChecklist.objects.create(
            created_by=user_id,
            artifact_id=artifact_id,
            title=title,
            description=description,
            query=query,
        )
        _bulk_create_sections(checklist.id, sections, created_by=user_id)
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

    def soft_delete(self, checklist: ArtifactChecklist, deleted_by: int) -> None:
        checklist.delete(deleted_by=deleted_by)

    def get_item(self, checklist_id: int, item_id: int) -> Optional[ArtifactChecklistItem]:
        return (
            ArtifactChecklistItem.objects
            .select_related("section", "section__checklist")
            .filter(id=item_id, section__checklist_id=checklist_id)
            .first()
        )

    def set_item_checked(self, item: ArtifactChecklistItem, is_checked: bool) -> ArtifactChecklistItem:
        item.is_checked = is_checked
        item.save(update_fields=["is_checked"])
        return item


checklist_repository = ChecklistRepository()
