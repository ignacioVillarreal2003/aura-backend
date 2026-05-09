"""Legacy URL aliases kept solely for backwards compatibility.

The aura-auth-service `notification_client` posts to:

    /api/internal/notification/admin-create/

so we expose that exact path here in addition to the new
`/api/v1/internal/notifications/admin-create/`. New callers MUST use
the v1 URL.
"""

from django.urls import path

from apps.notification.api.views.internal_views import LegacyAdminCreateView

urlpatterns = [
    path(
        "notification/admin-create/",
        LegacyAdminCreateView.as_view(),
        name="legacy-admin-create",
    ),
    # Defensive alias: some callers used the plural form.
    path(
        "notifications/admin-create/",
        LegacyAdminCreateView.as_view(),
        name="legacy-admin-create-plural",
    ),
]
