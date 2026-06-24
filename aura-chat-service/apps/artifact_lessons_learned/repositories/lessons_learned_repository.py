import logging
from typing import Optional
from django.db.models import Count
from django.db.models.query import Prefetch

from apps.artifact_lessons_learned.models import ArtifactLessonsLearned, ArtifactLessonsLearnedItem

logger = logging.getLogger(__name__)

_ITEMS_PREFETCH = Prefetch("items", queryset=ArtifactLessonsLearnedItem.objects.order_by("position"))


def _with_prefetch(qs):
    return qs.select_related("artifact").prefetch_related(_ITEMS_PREFETCH)


def _with_counts(qs):
    return qs.select_related("artifact").annotate(item_count=Count("items", distinct=True))


def _bulk_create_items(lessons_learned_id: int, items: list, created_by: int) -> None:
    item_objs = [
        ArtifactLessonsLearnedItem(
            lessons_learned_id=lessons_learned_id,
            category=item["category"],
            observation=item["observation"],
            discussion=str(item.get("discussion", "")),
            recommendation=str(item.get("recommendation", "")),
            position=item["position"],
            created_by=created_by,
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
            description: str = "",
            artifact_id: int,
            title: str = "",
            query: str = "",
    ) -> ArtifactLessonsLearned:
        ll = ArtifactLessonsLearned.objects.create(
            created_by=user_id,
            description=description,
            artifact_id=artifact_id,
            title=title,
            query=query,
        )
        _bulk_create_items(ll.id, items, created_by=user_id)
        return _with_prefetch(ArtifactLessonsLearned.objects.filter(id=ll.id)).first()

    def get_by_id(self, lessons_learned_id: int) -> Optional[ArtifactLessonsLearned]:
        return _with_prefetch(ArtifactLessonsLearned.objects.filter(id=lessons_learned_id)).first()

    def get_by_id_for_update(self, lessons_learned_id: int) -> Optional[ArtifactLessonsLearned]:
        return ArtifactLessonsLearned.objects.select_for_update().select_related("artifact").filter(
            id=lessons_learned_id).first()

    def list_by_user(self, user_id: int):
        return _with_counts(ArtifactLessonsLearned.objects.filter(created_by=user_id))

    def list_by_chat(self, source_chat_id: int):
        return _with_counts(ArtifactLessonsLearned.objects.filter(artifact__source_chat_id=source_chat_id))

    def list_all(self):
        return _with_counts(ArtifactLessonsLearned.objects.all())

    def soft_delete(self, ll: ArtifactLessonsLearned, deleted_by: int) -> None:
        ll.delete(deleted_by=deleted_by)


lessons_learned_repository = LessonsLearnedRepository()
