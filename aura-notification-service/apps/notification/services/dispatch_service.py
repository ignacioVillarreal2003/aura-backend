"""Pipeline that materialises an event into notifications and dispatches.

For every recipient the dispatcher:

1. Resolves the user preferences and decides which channels apply.
2. Honours idempotency via `event_key` (the database has a partial
   unique index on `(receiver_id, event_key)` for active rows).
3. Writes the in-app `Notification` row when the inapp channel is
   enabled, and publishes a realtime frame on `transaction.on_commit`.
4. Logs every channel decision in `notification_dispatch`.
5. Schedules an email Celery task for the email channel (the worker
   updates the dispatch row with the final status).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Optional

from django.db import IntegrityError, transaction

from apps.notification.events import EventDefinition, get_event
from apps.notification.models import (
    DispatchChannel,
    DispatchStatus,
    Notification,
    NotificationDispatch,
    NotificationStatus,
    NotificationType,
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
    channels: dict[str, str] = field(default_factory=dict)  # channel -> status
    suppressed: bool = False

    def to_dict(self) -> dict:
        return {
            "receiver_id": self.receiver_id,
            "notification_id": self.notification_id,
            "channels": self.channels,
            "suppressed": self.suppressed,
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
        idempotency_key: Optional[str] = None,
        link_url: Optional[str] = None,
        channels_override: Optional[Iterable[str]] = None,
        target_scope: str = "individual",
        target_label: Optional[str] = None,
    ) -> list[DispatchOutcome]:
        event = get_event(event_type)
        context = dict(context or {})
        if actor_name and "actor_name" not in context:
            context["actor_name"] = actor_name
        outcomes: list[DispatchOutcome] = []
        forced_channels = (
            tuple(channels_override) if channels_override else None
        )
        for receiver_id in recipient_ids:
            outcomes.append(
                self._dispatch_one(
                    event=event,
                    receiver_id=receiver_id,
                    actor_id=actor_id,
                    actor_name=actor_name,
                    context=context,
                    idempotency_key=idempotency_key,
                    link_url=link_url,
                    forced_channels=forced_channels,
                    target_scope=target_scope,
                    target_label=target_label,
                )
            )
        return outcomes

    # ------------------------------------------------------------------
    def _dispatch_one(
        self,
        *,
        event: EventDefinition,
        receiver_id: int,
        actor_id: Optional[int],
        actor_name: Optional[str],
        context: dict,
        idempotency_key: Optional[str],
        link_url: Optional[str],
        forced_channels: Optional[tuple[str, ...]],
        target_scope: str,
        target_label: Optional[str],
    ) -> DispatchOutcome:
        outcome = DispatchOutcome(receiver_id=receiver_id, notification_id=None)

        prefs = preference_service.get_global(receiver_id)
        overrides = preference_service.event_override_map(receiver_id)
        candidate_channels = forced_channels or event.default_channels

        decisions: dict[str, tuple[bool, str]] = {}
        for channel in candidate_channels:
            decision = preference_service.decide(
                receiver_id, event, channel, prefs=prefs, overrides=overrides
            )
            decisions[channel] = (decision.delivered, decision.reason)

        # ---- in-app channel ----
        notification_id: Optional[int] = None
        link = link_url or event.link_builder(context) if event.link_builder else link_url
        if PreferenceChannel.INAPP in decisions:
            delivered, reason = decisions[PreferenceChannel.INAPP]
            if delivered:
                rendered = template_service.render_inapp(event, {**context, "link_url": link})
                notification, was_suppressed = self._create_notification_row(
                    event=event,
                    receiver_id=receiver_id,
                    actor_id=actor_id,
                    actor_name=actor_name,
                    message=rendered.message,
                    data=context,
                    idempotency_key=idempotency_key,
                    link_url=rendered.link_url,
                    target_scope=target_scope,
                    target_label=target_label,
                )
                notification_id = notification.id if notification else None
                if was_suppressed:
                    outcome.suppressed = True
                    outcome.channels[PreferenceChannel.INAPP] = DispatchStatus.SUPPRESSED
                else:
                    outcome.channels[PreferenceChannel.INAPP] = DispatchStatus.SENT
                    self._log_dispatch(
                        notification=notification,
                        receiver_id=receiver_id,
                        event_type=event.event_type,
                        channel=DispatchChannel.INAPP,
                        status=DispatchStatus.SENT,
                        metadata={"reason": "ok"},
                        sent=True,
                    )
                    if notification is not None:
                        self._publish_created(receiver_id, notification)
            else:
                outcome.channels[PreferenceChannel.INAPP] = DispatchStatus.SKIPPED
                self._log_dispatch(
                    notification=None,
                    receiver_id=receiver_id,
                    event_type=event.event_type,
                    channel=DispatchChannel.INAPP,
                    status=DispatchStatus.SKIPPED,
                    metadata={"reason": reason},
                )

        outcome.notification_id = notification_id

        # ---- email channel ----
        if PreferenceChannel.EMAIL in decisions:
            delivered, reason = decisions[PreferenceChannel.EMAIL]
            if delivered:
                dispatch_row = self._log_dispatch(
                    notification=Notification(id=notification_id) if notification_id else None,
                    receiver_id=receiver_id,
                    event_type=event.event_type,
                    channel=DispatchChannel.EMAIL,
                    status=DispatchStatus.PENDING,
                    metadata={"reason": "queued"},
                )
                self._enqueue_email(
                    dispatch_id=dispatch_row.id,
                    event_type=event.event_type,
                    receiver_id=receiver_id,
                    context={
                        **context,
                        "actor_name": actor_name or context.get("actor_name"),
                        "link_url": link,
                    },
                )
                outcome.channels[PreferenceChannel.EMAIL] = DispatchStatus.PENDING
            else:
                outcome.channels[PreferenceChannel.EMAIL] = DispatchStatus.SKIPPED
                self._log_dispatch(
                    notification=Notification(id=notification_id) if notification_id else None,
                    receiver_id=receiver_id,
                    event_type=event.event_type,
                    channel=DispatchChannel.EMAIL,
                    status=DispatchStatus.SKIPPED,
                    metadata={"reason": reason},
                )

        return outcome

    # ------------------------------------------------------------------
    def _create_notification_row(
        self,
        *,
        event: EventDefinition,
        receiver_id: int,
        actor_id: Optional[int],
        actor_name: Optional[str],
        message: str,
        data: dict,
        idempotency_key: Optional[str],
        link_url: Optional[str],
        target_scope: str,
        target_label: Optional[str],
    ) -> tuple[Optional[Notification], bool]:
        try:
            notification = Notification(
                receiver_id=receiver_id,
                message=message,
                type=event.type,
                event_type=event.event_type,
                event_key=idempotency_key,
                data=data,
                link_url=link_url,
                severity=event.severity,
                target_scope=target_scope,
                target_label=target_label,
                sender_name=actor_name,
                status=NotificationStatus.UNREAD,
                created_by=actor_id,
                updated_by=actor_id,
            )
            notification.save()
            return notification, False
        except IntegrityError:
            # Duplicate idempotency key — find the existing one.
            existing = Notification.objects.filter(
                receiver_id=receiver_id,
                event_key=idempotency_key,
                deleted_at__isnull=True,
            ).first()
            return existing, True

    # ------------------------------------------------------------------
    def _log_dispatch(
        self,
        *,
        notification: Optional[Notification],
        receiver_id: int,
        event_type: str,
        channel: str,
        status: str,
        metadata: dict,
        sent: bool = False,
    ) -> NotificationDispatch:
        from django.utils import timezone as dj_timezone

        return NotificationDispatch.objects.create(
            notification_id=notification.id if notification and getattr(notification, "id", None) else None,
            receiver_id=receiver_id,
            event_type=event_type,
            channel=channel,
            status=status,
            attempt=1 if sent else 0,
            metadata=metadata,
            sent_at=dj_timezone.now() if sent else None,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _publish_created(receiver_id: int, notification: Notification) -> None:
        payload = {
            "id": notification.id,
            "message": notification.message,
            "type": notification.type,
            "event_type": notification.event_type,
            "severity": notification.severity,
            "status": notification.status,
            "link_url": notification.link_url,
            "data": notification.data,
            "created_at": notification.created_at.isoformat() if notification.created_at else None,
        }

        def _publish():
            try:
                realtime_service.publish_created(receiver_id, payload)
            except Exception:
                logger.exception("Failed to publish realtime created event.")

        # Defer the publish until after the transaction commits.
        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(_publish)
        else:
            _publish()

    # ------------------------------------------------------------------
    @staticmethod
    def _enqueue_email(
        *,
        dispatch_id: int,
        event_type: str,
        receiver_id: int,
        context: dict,
    ) -> None:
        # Lazy import to avoid pulling Celery during model migrations / admin.
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
                NotificationDispatch.objects.filter(pk=dispatch_id).update(
                    status=DispatchStatus.FAILED,
                    error="failed_to_enqueue",
                )

        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(_enqueue)
        else:
            _enqueue()


dispatch_service = DispatchService()
