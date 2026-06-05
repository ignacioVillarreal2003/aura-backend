import logging
from typing import Optional
from django.db import transaction
from django.db.models import Count
from django.db.models.query import Prefetch

from apps.artifact_lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem

logger = logging.getLogger(__name__)

_ITEMS_PREFETCH = Prefetch("items", queryset=ArtifactLessonsLearnedItem.objects.order_by("position"))


def _with_prefetch(qs):
    return qs.select_related("artifact").prefetch_related(_ITEMS_PREFETCH)


def _with_counts(qs):
    return qs.select_related("artifact").annotate(item_count=Count("items", distinct=True))


def _bulk_create_items(lessons_learned_id: int, items: list) -> None:
    item_objs = [
        ArtifactLessonsLearnedItem(
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
        ArtifactLessonsLearnedItem.objects.bulk_create(item_objs)


class LessonsLearnedRepository:
    def create(
            self,
            *,
            user_id: int,
            items: list,
            context: str = "",
            artifact_id: int,
    ) -> ArtifactLessonsLearned:
        ll = ArtifactLessonsLearned.objects.create(
            created_by=user_id,
            context=context,
            artifact_id=artifact_id,
        )
        _bulk_create_items(ll.id, items)
        return _with_prefetch(ArtifactLessonsLearned.objects.filter(id=ll.id)).first()

    def get_by_id(self, lessons_learned_id: int) -> Optional[ArtifactLessonsLearned]:
        return _with_prefetch(ArtifactLessonsLearned.objects.filter(id=lessons_learned_id)).first()

    def list_by_user(self, user_id: int):
        return _with_counts(ArtifactLessonsLearned.objects.filter(created_by=user_id))

    def list_by_chat(self, source_chat_id: int):
        return _with_counts(ArtifactLessonsLearned.objects.filter(artifact__source_chat_id=source_chat_id))

    def list_all(self):
        return _with_counts(ArtifactLessonsLearned.objects.all())

    @transaction.atomic
    def update(
            self,
            ll: ArtifactLessonsLearned,
            *,
            updated_by: int,
            context: Optional[str] = None,
            items: Optional[list] = None,
    ) -> ArtifactLessonsLearned:
        update_fields = []
        if context is not None:
            ll.context = context
            update_fields.append("context")
        if items is not None:
            ArtifactLessonsLearnedItem.objects.filter(lessons_learned_id=ll.id).delete()
            _bulk_create_items(ll.id, items)
        if update_fields:
            ll.updated_by = updated_by
            update_fields.append("updated_by")
            ll.save(update_fields=update_fields)
        elif items is not None:
            ll.updated_by = updated_by
            ll.save(update_fields=["updated_by"])
        return _with_prefetch(ArtifactLessonsLearned.objects.filter(id=ll.id)).first()

    def soft_delete(self, ll: ArtifactLessonsLearned, deleted_by: int) -> None:
        ll.delete(deleted_by=deleted_by)


lessons_learned_repository = LessonsLearnedRepository()
