"""High-level facade used by the public API and the legacy admin path.

Wraps inbox CRUD operations on top of the persistence layer and the
dispatcher. Realtime events for status/delete updates are also published
here so the SSE clients see status flips instantly.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from apps.notification.events.registry import EventType
from apps.notification.models import (
    Notification,
    NotificationStatus,
)
from apps.notification.services.dispatch_service import DispatchOutcome, dispatch_service
from apps.notification.services.realtime_service import realtime_service
from core.exceptions.base import NotFoundException, ValidationException

logger = logging.getLogger(__name__)


class NotificationService:
    # ------------------------------------------------------------------
    # Inbox queries (scoped to a single user).
    # ------------------------------------------------------------------
    def list_for_user(
        self,
        user_id: int,
        *,
        status_in: Optional[Iterable[str]] = None,
        event_type: Optional[str] = None,
        type: Optional[str] = None,
        since: Optional[datetime] = None,
        unread_only: bool = False,
    ):
        qs = Notification.objects.filter(receiver_id=user_id, deleted_at__isnull=True)
        if status_in:
            qs = qs.filter(status__in=list(status_in))
        if unread_only:
            qs = qs.filter(status=NotificationStatus.UNREAD)
        if event_type:
            qs = qs.filter(event_type=event_type)
        if type:
            qs = qs.filter(type=type)
        if since:
            qs = qs.filter(created_at__gte=since)
        return qs.order_by("-created_at", "-id")

    def get_for_user(self, user_id: int, notification_id: int) -> Notification:
        notification = Notification.objects.filter(
            pk=notification_id,
            receiver_id=user_id,
            deleted_at__isnull=True,
        ).first()
        if notification is None:
            raise NotFoundException("Notification not found.", error_code="notification_not_found")
        return notification

    def unread_count(self, user_id: int) -> int:
        return Notification.objects.filter(
            receiver_id=user_id,
            status=NotificationStatus.UNREAD,
            deleted_at__isnull=True,
        ).count()

    # ------------------------------------------------------------------
    # State mutations.
    # ------------------------------------------------------------------
    def update_status(
        self,
        user_id: int,
        notification_id: int,
        new_status: str,
    ) -> Notification:
        if new_status not in NotificationStatus.values:
            raise ValidationException(
                detail=f"Invalid status '{new_status}'.",
                error_code="invalid_status",
            )
        notification = self.get_for_user(user_id, notification_id)

        if new_status == NotificationStatus.READ:
            notification.mark_read(updated_by=user_id)
        elif new_status == NotificationStatus.UNREAD:
            notification.mark_unread(updated_by=user_id)
        else:
            notification.archive(updated_by=user_id)

        realtime_service.publish_updated(
            user_id,
            {"id": notification.id, "status": notification.status},
        )
        return notification

    def mark_all_read(self, user_id: int, *, until_id: Optional[int] = None) -> int:
        qs = Notification.objects.filter(
            receiver_id=user_id,
            status=NotificationStatus.UNREAD,
            deleted_at__isnull=True,
        )
        if until_id is not None:
            qs = qs.filter(id__lte=until_id)
        now = timezone.now()
        updated = qs.update(
            status=NotificationStatus.READ,
            read_at=now,
            updated_by=user_id,
            updated_at=now,
        )
        if updated:
            realtime_service.publish_updated(
                user_id,
                {"all_marked_read": True, "until_id": until_id, "count": updated},
            )
        return updated

    def soft_delete(self, user_id: int, notification_id: int) -> None:
        notification = self.get_for_user(user_id, notification_id)
        notification.soft_delete(deleted_by=user_id)
        realtime_service.publish_deleted(user_id, notification.id)

    def hard_delete(self, notification_id: int) -> None:
        notification = Notification.objects.filter(pk=notification_id).first()
        if notification is None:
            raise NotFoundException("Notification not found.", error_code="notification_not_found")
        receiver_id = notification.receiver_id
        notification_pk = notification.id
        notification.delete()
        realtime_service.publish_deleted(receiver_id, notification_pk)

    # ------------------------------------------------------------------
    # Producer-facing entry points (used by the internal API).
    # ------------------------------------------------------------------
    def emit_event(self, **kwargs) -> list[DispatchOutcome]:
        with transaction.atomic():
            return dispatch_service.dispatch_event(**kwargs)

    def admin_broadcast(
        self,
        *,
        receiver_ids: Iterable[int],
        message: str,
        actor_user_id: Optional[int],
        actor_name: Optional[str] = None,
        target_scope: str = "individual",
        target_label: Optional[str] = None,
        send_email: bool = False,
        subject: Optional[str] = None,
    ) -> list[DispatchOutcome]:
        from apps.notification.models import PreferenceChannel

        channels_override = None
        if send_email:
            channels_override = (PreferenceChannel.INAPP, PreferenceChannel.EMAIL)
        with transaction.atomic():
            return dispatch_service.dispatch_event(
                event_type=EventType.ADMIN_BROADCAST,
                recipient_ids=list(receiver_ids),
                actor_id=actor_user_id,
                actor_name=actor_name,
                context={"message": message, "subject": subject or "Mensaje de un administrador"},
                idempotency_key=None,
                link_url=None,
                channels_override=channels_override,
                target_scope=target_scope,
                target_label=target_label,
            )


notification_service = NotificationService()
