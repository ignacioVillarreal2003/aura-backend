from django.urls import path

from apps.notification.api.views.event_type_views import EventTypeCatalogueView
from apps.notification.api.views.health_view import health_check
from apps.notification.api.views.internal_views import (
    InternalEventEmissionView,
    LegacyAdminCreateView,
)
from apps.notification.api.views.notification_views import (
    MarkAllReadView,
    NotificationDetailView,
    NotificationHardDeleteView,
    NotificationListView,
    NotificationUnreadCountView,
)
from apps.notification.api.views.preference_views import (
    EventPreferenceDetailView,
    EventPreferenceListView,
    GlobalPreferenceView,
)
from apps.notification.api.views.stream_view import NotificationStreamView

app_name = "notifications-v1"

urlpatterns = [
    path("health", health_check, name="health"),
    # Inbox
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/unread-count/", NotificationUnreadCountView.as_view(), name="notification-unread-count"),
    path("notifications/mark-all-read/", MarkAllReadView.as_view(), name="notification-mark-all-read"),
    path("notifications/stream/", NotificationStreamView.as_view(), name="notification-stream"),
    path("notifications/<int:pk>/", NotificationDetailView.as_view(), name="notification-detail"),
    path("notifications/<int:pk>/hard/", NotificationHardDeleteView.as_view(), name="notification-hard-delete"),
    # Preferences
    path("me/notification-preferences/", GlobalPreferenceView.as_view(), name="prefs-global"),
    path(
        "me/notification-preferences/event-types/",
        EventPreferenceListView.as_view(),
        name="prefs-events",
    ),
    path(
        "me/notification-preferences/event-types/<str:event_type>/",
        EventPreferenceDetailView.as_view(),
        name="prefs-event-detail",
    ),
    # Catalogue
    path("event-types/", EventTypeCatalogueView.as_view(), name="event-types"),
    # Internal (service-to-service, X-Internal-Token)
    path(
        "internal/events/",
        InternalEventEmissionView.as_view(),
        name="internal-events",
    ),
    path(
        "internal/notifications/admin-create/",
        LegacyAdminCreateView.as_view(),
        name="internal-admin-create",
    ),
]
