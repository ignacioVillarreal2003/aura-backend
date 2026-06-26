"""Notifications models package (auth-service mirror)."""

from apps.notifications.models.notification import (
    Notification,
    NotificationEventType,
    NotificationSeverity,
    NotificationStatus,
    IndividualNotification,
    GroupNotification,
)

__all__ = [
    'Notification',
    'NotificationEventType',
    'NotificationSeverity',
    'NotificationStatus',
    'IndividualNotification',
    'GroupNotification',
]
