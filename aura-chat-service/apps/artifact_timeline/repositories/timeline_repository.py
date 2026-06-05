import logging
from typing import Optional
from django.db import transaction
from django.db.models import Count
from django.db.models.query import Prefetch

from apps.artifact_timeline.models import ArtifactTimeline, ArtifactTimelineEvent

logger = logging.getLogger(__name__)

_EVENTS_PREFETCH = Prefetch("events", queryset=ArtifactTimelineEvent.objects.order_by("position"))


def _with_prefetch(qs):
    return qs.select_related("artifact").prefetch_related(_EVENTS_PREFETCH)


def _with_counts(qs):
    return qs.select_related("artifact").annotate(event_count=Count("events", distinct=True))


def _bulk_create_events(timeline_id: int, events: list) -> None:
    event_objs = [
        ArtifactTimelineEvent(
            timeline_id=timeline_id,
            title=ev["title"],
            description=str(ev.get("description", "")),
            occurred_at=ev.get("occurred_at"),
            occurred_label=str(ev.get("occurred_label", "")),
            position=ev["position"],
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
            summary: str = "",
            artifact_id: int,
    ) -> ArtifactTimeline:
        timeline = ArtifactTimeline.objects.create(
            created_by=user_id,
            summary=summary,
            artifact_id=artifact_id,
        )
        _bulk_create_events(timeline.id, events)
        return _with_prefetch(ArtifactTimeline.objects.filter(id=timeline.id)).first()

    def get_by_id(self, timeline_id: int) -> Optional[ArtifactTimeline]:
        return _with_prefetch(ArtifactTimeline.objects.filter(id=timeline_id)).first()

    def list_by_user(self, user_id: int):
        return _with_counts(ArtifactTimeline.objects.filter(created_by=user_id))

    def list_by_chat(self, source_chat_id: int):
        return _with_counts(ArtifactTimeline.objects.filter(artifact__source_chat_id=source_chat_id))

    def list_all(self):
        return _with_counts(ArtifactTimeline.objects.all())

    @transaction.atomic
    def update(
            self,
            timeline: ArtifactTimeline,
            *,
            updated_by: int,
            summary: Optional[str] = None,
            events: Optional[list] = None,
    ) -> ArtifactTimeline:
        update_fields = []
        if summary is not None:
            timeline.summary = summary
            update_fields.append("summary")
        if events is not None:
            ArtifactTimelineEvent.objects.filter(timeline_id=timeline.id).delete()
            _bulk_create_events(timeline.id, events)
        if update_fields:
            timeline.updated_by = updated_by
            update_fields.append("updated_by")
            timeline.save(update_fields=update_fields)
        elif events is not None:
            timeline.updated_by = updated_by
            timeline.save(update_fields=["updated_by"])
        return _with_prefetch(ArtifactTimeline.objects.filter(id=timeline.id)).first()

    def soft_delete(self, timeline: ArtifactTimeline, deleted_by: int) -> None:
        timeline.delete(deleted_by=deleted_by)


timeline_repository = TimelineRepository()
