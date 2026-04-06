"""Notification API URL routes."""

from django.urls import path
from notifications.api.views import (
    NotificationListCreateView,
    NotificationStatusView,
    NotificationDeleteView,
    NotificationHardDeleteView,
    InternalAdminNotificationCreateView,
)

urlpatterns = [
    path('notifications/', NotificationListCreateView.as_view(), name='notification-list-create'),
    path('notifications/<int:pk>/status/', NotificationStatusView.as_view(), name='notification-status'),
    path('notifications/<int:pk>/', NotificationDeleteView.as_view(), name='notification-delete'),
    path('notifications/<int:pk>/hard/', NotificationHardDeleteView.as_view(), name='notification-hard-delete'),
    path('internal/notifications/admin-create/', InternalAdminNotificationCreateView.as_view(), name='internal-admin-notification-create'),
]
