from __future__ import annotations
import logging
from datetime import datetime
from typing import Iterable, Optional
from django.utils import timezone

from apps.notification.models import Notification, NotificationStatus
from apps.notification.services.dispatch_service import DispatchOutcome, dispatch_service
from apps.notification.services.realtime_service import realtime_service
from core.exceptions.base import NotFoundException, ValidationException

logger = logging.getLogger(__name__)


class NotificationService:
    def list_for_user(
        self,
        user_id: int,
        *,
        status_in: Optional[Iterable[str]] = None,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
    ):
        qs = Notification.objects.filter(receiver_id=user_id)
        if status_in:
            qs = qs.filter(status__in=list(status_in))
        if event_type:
            qs = qs.filter(event_type=event_type)
        if since:
            qs = qs.filter(created_at__gte=since)
        return qs.order_by("-created_at", "-id")

    def get_for_user(self, user_id: int, notification_id: int) -> Notification:
        notification = Notification.objects.filter(
            pk=notification_id,
            receiver_id=user_id,
        ).first()
        if notification is None:
            raise NotFoundException("Notification not found.", error_code="notification_not_found")
        return notification

    def unread_count(self, user_id: int) -> int:
        return Notification.objects.filter(
            receiver_id=user_id,
            status=NotificationStatus.UNREAD,
        ).count()

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
            notification.mark_read()
        else:
            notification.mark_unread()

        realtime_service.publish_updated(
            user_id,
            {"id": notification.id, "status": notification.status},
        )
        return notification

    _MARK_ALL_READ_BATCH = 1000

    def mark_all_read(self, user_id: int, *, until_id: Optional[int] = None) -> int:
        qs = Notification.objects.filter(
            receiver_id=user_id,
            status=NotificationStatus.UNREAD,
        )
        if until_id is not None:
            qs = qs.filter(id__lte=until_id)
        ids = list(qs.values_list("id", flat=True)[: self._MARK_ALL_READ_BATCH])
        if not ids:
            return 0
        now = timezone.now()
        updated = Notification.objects.filter(id__in=ids).update(
            status=NotificationStatus.READ,
            read_at=now,
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

    def emit_event(self, **kwargs) -> list[DispatchOutcome]:
        return dispatch_service.dispatch_event(**kwargs)


notification_service = NotificationService()
