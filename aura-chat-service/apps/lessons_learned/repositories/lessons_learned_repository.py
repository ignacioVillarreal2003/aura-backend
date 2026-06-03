import logging
from typing import Optional
from django.db.models import Count
from django.db.models.query import Prefetch

from apps.lessons_learned.models import LessonsLearned, LessonsLearnedItem

logger = logging.getLogger(__name__)

_ITEMS_PREFETCH = Prefetch("items", queryset=LessonsLearnedItem.objects.order_by("position"))


def _with_prefetch(qs):
    return qs.prefetch_related(_ITEMS_PREFETCH)


def _with_counts(qs):
    return qs.annotate(item_count=Count("items", distinct=True))


def _bulk_create_items(lessons_learned_id: int, items: list) -> None:
    item_objs = [
        LessonsLearnedItem(
            lessons_learned_id=lessons_learned_id,
            category=item["category"],
            observation=item["observation"],
            discussion=str(item.get("discussion", "")),
            recommendation=str(item.get("recommendation", "")),
            position=item["position"],
        )
        for item in items
    ]
    if item_objs:
        LessonsLearnedItem.objects.bulk_create(item_objs)


class LessonsLearnedRepository:
    def create(
            self,
            *,
            user_id: int,
            title: str,
            items: list,
            mode: str,
            context: str = "",
            what_went_well: str = "",
            what_failed: str = "",
            recommendations: str = "",
            source_chat_id: Optional[int] = None,
            artifact_id: Optional[int] = None,
    ) -> LessonsLearned:
        ll = LessonsLearned.objects.create(
            created_by=user_id,
            title=title,
            context=context,
            what_went_well=what_went_well,
            what_failed=what_failed,
            recommendations=recommendations,
            mode=mode,
            source_chat_id=source_chat_id,
            artifact_id=artifact_id,
        )
        _bulk_create_items(ll.id, items)
        return _with_prefetch(LessonsLearned.objects.filter(id=ll.id)).first()

    def get_by_id(self, lessons_learned_id: int) -> Optional[LessonsLearned]:
        return _with_prefetch(LessonsLearned.objects.filter(id=lessons_learned_id)).first()

    def list_by_user(self, user_id: int):
        return _with_counts(LessonsLearned.objects.filter(created_by=user_id))

    def list_by_chat(self, source_chat_id: int):
        return _with_counts(LessonsLearned.objects.filter(source_chat_id=source_chat_id))

    def list_all(self):
        return _with_counts(LessonsLearned.objects.all())

    def update(
            self,
            ll: LessonsLearned,
            *,
            updated_by: int,
            title: Optional[str] = None,
            context: Optional[str] = None,
            what_went_well: Optional[str] = None,
            what_failed: Optional[str] = None,
            recommendations: Optional[str] = None,
            items: Optional[list] = None,
    ) -> LessonsLearned:
        update_fields = []
        for field, value in (
                ("title", title),
                ("context", context),
                ("what_went_well", what_went_well),
                ("what_failed", what_failed),
                ("recommendations", recommendations),
        ):
            if value is not None:
                setattr(ll, field, value)
                update_fields.append(field)
        if items is not None:
            LessonsLearnedItem.objects.filter(lessons_learned_id=ll.id).delete()
            _bulk_create_items(ll.id, items)
        if update_fields:
            ll.updated_by = updated_by
            update_fields.append("updated_by")
            ll.save(update_fields=update_fields)
        elif items is not None:
            ll.updated_by = updated_by
            ll.save(update_fields=["updated_by"])
        return _with_prefetch(LessonsLearned.objects.filter(id=ll.id)).first()

    def soft_delete(self, ll: LessonsLearned, deleted_by: int) -> None:
        ll.delete(deleted_by=deleted_by)


lessons_learned_repository = LessonsLearnedRepository()
