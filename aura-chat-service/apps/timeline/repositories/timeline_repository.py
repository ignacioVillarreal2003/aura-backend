import logging
from typing import Optional
from django.db.models.query import Prefetch

from apps.timeline.models import Timeline, TimelineEvent

logger = logging.getLogger(__name__)

_EVENTS_PREFETCH = Prefetch("events", queryset=TimelineEvent.objects.order_by("position"))


def _with_prefetch(qs):
    return qs.prefetch_related(_EVENTS_PREFETCH)


def _bulk_create_events(timeline_id: int, events: list) -> None:
    event_objs = [
        TimelineEvent(
            timeline_id=timeline_id,
            event=ev["event"],
            description=str(ev.get("description", "")),
            occurred_at=ev.get("occurred_at"),
            occurred_label=str(ev.get("occurred_label", "")),
            source_document_id=ev.get("source_document_id"),
            position=ev["position"],
        )
        for ev in events
    ]
    if event_objs:
        TimelineEvent.objects.bulk_create(event_objs)


class TimelineRepository:
    def create(
            self,
            *,
            user_id: int,
            title: str,
            events: list,
            mode: str,
            summary: str = "",
            source_chat_id: Optional[int] = None,
            artifact_id: Optional[int] = None,
    ) -> Timeline:
        timeline = Timeline.objects.create(
            created_by=user_id,
            title=title,
            summary=summary,
            mode=mode,
            source_chat_id=source_chat_id,
            artifact_id=artifact_id,
        )
        _bulk_create_events(timeline.id, events)
        return _with_prefetch(Timeline.objects.filter(id=timeline.id)).first()

    def get_by_id(self, timeline_id: int) -> Optional[Timeline]:
        return _with_prefetch(Timeline.objects.filter(id=timeline_id)).first()

    def list_by_user(self, user_id: int):
        return Timeline.objects.filter(created_by=user_id)

    def list_by_chat(self, source_chat_id: int):
        return Timeline.objects.filter(source_chat_id=source_chat_id)

    def list_all(self):
        return Timeline.objects.all()

    def update(
            self,
            timeline: Timeline,
            *,
            updated_by: int,
            title: Optional[str] = None,
            summary: Optional[str] = None,
            events: Optional[list] = None,
    ) -> Timeline:
        update_fields = []
        if title is not None:
            timeline.title = title
            update_fields.append("title")
        if summary is not None:
            timeline.summary = summary
            update_fields.append("summary")
        if events is not None:
            TimelineEvent.objects.filter(timeline_id=timeline.id).delete()
            _bulk_create_events(timeline.id, events)
        if update_fields:
            timeline.updated_by = updated_by
            update_fields.append("updated_by")
            timeline.save(update_fields=update_fields)
        elif events is not None:
            timeline.updated_by = updated_by
            timeline.save(update_fields=["updated_by"])
        return _with_prefetch(Timeline.objects.filter(id=timeline.id)).first()

    def soft_delete(self, timeline: Timeline, deleted_by: int) -> None:
        timeline.delete(deleted_by=deleted_by)


timeline_repository = TimelineRepository()
