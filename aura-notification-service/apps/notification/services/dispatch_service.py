from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional
from django.db import transaction

from apps.notification.events import EventDefinition, get_event
from apps.notification.models import (
    EmailDispatch,
    EmailDispatchStatus,
    Notification,
    NotificationStatus,
    PreferenceChannel,
)
from apps.notification.services.preference_service import preference_service
from apps.notification.services.realtime_service import realtime_service
from apps.notification.services.template_service import template_service

logger = logging.getLogger(__name__)


@dataclass
class DispatchOutcome:
    receiver_id: int
    notification_id: Optional[int]
    channels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "receiver_id": self.receiver_id,
            "notification_id": self.notification_id,
            "channels": self.channels,
        }


class DispatchService:
    def dispatch_event(
        self,
        *,
        event_type: str,
        recipient_ids: Iterable[int],
        actor_id: Optional[int],
        actor_name: Optional[str],
        context: Optional[dict] = None,
        link_url: Optional[str] = None,
    ) -> list[DispatchOutcome]:
        event = get_event(event_type)
        context = dict(context or {})
        if actor_name and "actor_name" not in context:
            context["actor_name"] = actor_name
        all_ids = list(recipient_ids)
        prefs_map = preference_service.get_global_map(all_ids)
        return [
            self._dispatch_one(
                event=event,
                receiver_id=receiver_id,
                actor_id=actor_id,
                actor_name=actor_name,
                context=context,
                link_url=link_url,
                prefetched_prefs=prefs_map.get(receiver_id),
            )
            for receiver_id in all_ids
        ]

    def _dispatch_one(
        self,
        *,
        event: EventDefinition,
        receiver_id: int,
        actor_id: Optional[int],
        actor_name: Optional[str],
        context: dict,
        link_url: Optional[str],
        prefetched_prefs=None,
    ) -> DispatchOutcome:
        outcome = DispatchOutcome(receiver_id=receiver_id, notification_id=None)
        prefs = prefetched_prefs if prefetched_prefs is not None else preference_service.get_global(receiver_id)

        decisions: dict[str, tuple[bool, str]] = {}
        for channel in event.default_channels:
            decision = preference_service.decide(
                receiver_id, event, channel, prefs=prefs
            )
            decisions[channel] = (decision.delivered, decision.reason)

        notification_id: Optional[int] = None
        link = link_url or (event.link_builder(context) if event.link_builder else None)

        if PreferenceChannel.INAPP in decisions:
            delivered, _reason = decisions[PreferenceChannel.INAPP]
            if delivered:
                rendered = template_service.render_inapp(event, {**context, "link_url": link})
                notification = self._create_notification_row(
                    event=event,
                    receiver_id=receiver_id,
                    actor_id=actor_id,
                    actor_name=actor_name,
                    message=rendered.message,
                    data=context,
                    link_url=rendered.link_url,
                )
                notification_id = notification.id
                outcome.channels[PreferenceChannel.INAPP] = EmailDispatchStatus.SENT
                self._publish_created(receiver_id, notification)
            else:
                outcome.channels[PreferenceChannel.INAPP] = EmailDispatchStatus.SKIPPED

        outcome.notification_id = notification_id

        if PreferenceChannel.EMAIL in decisions:
            delivered, reason = decisions[PreferenceChannel.EMAIL]
            if delivered:
                dispatch_row = EmailDispatch.objects.create(
                    receiver_id=receiver_id,
                    event_type=event.event_type,
                    status=EmailDispatchStatus.PENDING,
                    payload={
                        **context,
                        "actor_name": actor_name or context.get("actor_name"),
                        "link_url": link,
                    },
                )
                self._enqueue_email(
                    dispatch_id=dispatch_row.id,
                    event_type=event.event_type,
                    receiver_id=receiver_id,
                    context=dispatch_row.payload,
                )
                outcome.channels[PreferenceChannel.EMAIL] = EmailDispatchStatus.PENDING
            else:
                outcome.channels[PreferenceChannel.EMAIL] = EmailDispatchStatus.SKIPPED
                EmailDispatch.objects.create(
                    receiver_id=receiver_id,
                    event_type=event.event_type,
                    status=EmailDispatchStatus.SKIPPED,
                    error=reason,
                    payload=context,
                )

        return outcome

    def _create_notification_row(
        self,
        *,
        event: EventDefinition,
        receiver_id: int,
        actor_id: Optional[int],
        actor_name: Optional[str],
        message: str,
        data: dict,
        link_url: Optional[str],
    ) -> Notification:
        notification = Notification(
            receiver_id=receiver_id,
            event_type=event.event_type,
            message=message,
            data=data,
            link_url=link_url,
            severity=event.severity,
            actor_name=actor_name,
            status=NotificationStatus.UNREAD,
            created_by=actor_id,
        )
        notification.save()
        return notification

    @staticmethod
    def _publish_created(receiver_id: int, notification: Notification) -> None:
        payload = {
            "id": notification.id,
            "receiver_id": notification.receiver_id,
            "message": notification.message,
            "event_type": notification.event_type,
            "severity": notification.severity,
            "status": notification.status,
            "link_url": notification.link_url,
            "data": notification.data,
            "actor_name": notification.actor_name,
            "read_at": None,
            "created_by": notification.created_by,
            "created_at": notification.created_at.isoformat() if notification.created_at else None,
        }

        def _publish():
            try:
                realtime_service.publish_created(receiver_id, payload)
            except Exception:
                logger.exception("Failed to publish realtime created event.")

        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(_publish)
        else:
            _publish()

    @staticmethod
    def _enqueue_email(
        *,
        dispatch_id: int,
        event_type: str,
        receiver_id: int,
        context: dict,
    ) -> None:
        from apps.notification.tasks.send_email import send_email_dispatch

        def _enqueue():
            try:
                send_email_dispatch.delay(
                    dispatch_id=dispatch_id,
                    event_type=event_type,
                    receiver_id=receiver_id,
                    context=context,
                )
            except Exception:
                logger.exception(
                    "Failed to enqueue email dispatch %s; marking failed.",
                    dispatch_id,
                )
                EmailDispatch.objects.filter(pk=dispatch_id).update(
                    status=EmailDispatchStatus.FAILED,
                    error="failed_to_enqueue",
                )

        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(_enqueue)
        else:
            _enqueue()


dispatch_service = DispatchService()
