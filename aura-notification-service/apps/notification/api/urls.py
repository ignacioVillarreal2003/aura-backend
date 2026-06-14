from django.urls import path

from apps.notification.api.views.event_type_views import EventTypeCatalogueView
from apps.notification.api.views.health_view import health_check
from apps.notification.api.views.internal_views import InternalEventEmissionView
from apps.notification.api.views.notification_views import (
    MarkAllReadView,
    NotificationDetailView,
    NotificationListView,
    NotificationUnreadCountView,
)
from apps.notification.api.views.preference_views import GlobalPreferenceView
from apps.notification.api.views.stream_view import NotificationStreamView

app_name = "notifications-v1"

urlpatterns = [
    path("health", health_check, name="health"),
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/unread-count/", NotificationUnreadCountView.as_view(), name="notification-unread-count"),
    path("notifications/mark-all-read/", MarkAllReadView.as_view(), name="notification-mark-all-read"),
    path("notifications/stream/", NotificationStreamView.as_view(), name="notification-stream"),
    path("notifications/<int:pk>/", NotificationDetailView.as_view(), name="notification-detail"),
    path("me/notification-preferences/", GlobalPreferenceView.as_view(), name="prefs-global"),
    path("event-types/", EventTypeCatalogueView.as_view(), name="event-types"),
    path(
        "internal/events/",
        InternalEventEmissionView.as_view(),
        name="internal-events",
    ),
]
