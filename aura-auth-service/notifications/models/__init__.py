"""Notifications models package (auth-service mirror)."""

from notifications.models.notification import (
    Notification,
    NotificationEventType,
    NotificationSeverity,
    NotificationStatus,
    IndividualNotification,
    GroupNotification,
    SystemNotification,
)

__all__ = [
    'Notification',
    'NotificationEventType',
    'NotificationSeverity',
    'NotificationStatus',
    'IndividualNotification',
    'GroupNotification',
    'SystemNotification',
]
