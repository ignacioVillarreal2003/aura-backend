import logging
from typing import Optional
from django.db.models import Count
from django.db.models.query import Prefetch

from apps.artifact_timeline.models import ArtifactTimeline, ArtifactTimelineEvent

logger = logging.getLogger(__name__)

_EVENTS_PREFETCH = Prefetch("events", queryset=ArtifactTimelineEvent.objects.order_by("position"))


def _with_prefetch(qs):
    return qs.select_related("artifact").prefetch_related(_EVENTS_PREFETCH)


def _with_counts(qs):
    return qs.select_related("artifact").annotate(event_count=Count("events", distinct=True))


def _bulk_create_events(timeline_id: int, events: list, created_by: int) -> None:
    event_objs = [
        ArtifactTimelineEvent(
            timeline_id=timeline_id,
            title=ev["title"],
            description=str(ev.get("description", "")),
            occurred_label=str(ev.get("occurred_label", "")),
            position=ev["position"],
            created_by=created_by,
        )
        for ev in events
    ]
    if event_objs:
        ArtifactTimelineEvent.objects.bulk_create(event_objs)


class TimelineRepository:
    def create(
            self,
            *,
            user_id: int,
            events: list,
            description: str = "",
            artifact_id: int,
            title: str = "",
            query: str = "",
    ) -> ArtifactTimeline:
        timeline = ArtifactTimeline.objects.create(
            created_by=user_id,
            description=description,
            artifact_id=artifact_id,
            title=title,
            query=query,
        )
        _bulk_create_events(timeline.id, events, created_by=user_id)
        return _with_prefetch(ArtifactTimeline.objects.filter(id=timeline.id)).first()

    def get_by_id(self, timeline_id: int) -> Optional[ArtifactTimeline]:
        return _with_prefetch(ArtifactTimeline.objects.filter(id=timeline_id)).first()

    def get_by_id_for_update(self, timeline_id: int) -> Optional[ArtifactTimeline]:
        return ArtifactTimeline.objects.select_for_update().select_related("artifact").filter(id=timeline_id).first()

    def list_by_user(self, user_id: int):
        return _with_counts(ArtifactTimeline.objects.filter(created_by=user_id))

    def list_by_chat(self, source_chat_id: int):
        return _with_counts(ArtifactTimeline.objects.filter(artifact__source_chat_id=source_chat_id))

    def list_all(self):
        return _with_counts(ArtifactTimeline.objects.all())

    def soft_delete(self, timeline: ArtifactTimeline, deleted_by: int) -> None:
        timeline.delete(deleted_by=deleted_by)


timeline_repository = TimelineRepository()
