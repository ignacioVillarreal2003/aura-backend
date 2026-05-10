# Notification-service application permissions.
#
# Issued by the central authentication service in the JWT `permissions` claim.
# Each end-user endpoint checks exactly one permission via
# `AccessControl.require_permissions(user, frozenset({...}))`.
#
# Internal routes (`X-Internal-Token`) do not use these strings.

from __future__ import annotations

# GET /api/v1/notifications/
NOTIFICATION_INBOX_LIST = "NOTIFICATION_INBOX_LIST"

# GET /api/v1/notifications/unread-count/
NOTIFICATION_UNREAD_COUNT_GET = "NOTIFICATION_UNREAD_COUNT_GET"

# GET /api/v1/notifications/stream/ (SSE)
NOTIFICATION_STREAM_SUBSCRIBE = "NOTIFICATION_STREAM_SUBSCRIBE"

# GET /api/v1/notifications/{id}/
NOTIFICATION_DETAIL_GET = "NOTIFICATION_DETAIL_GET"

# PATCH /api/v1/notifications/{id}/
NOTIFICATION_STATUS_PATCH = "NOTIFICATION_STATUS_PATCH"

# DELETE /api/v1/notifications/{id}/ (soft)
NOTIFICATION_SOFT_DELETE = "NOTIFICATION_SOFT_DELETE"

# POST /api/v1/notifications/mark-all-read/
NOTIFICATION_MARK_ALL_READ_POST = "NOTIFICATION_MARK_ALL_READ_POST"

# DELETE /api/v1/notifications/{id}/hard/
NOTIFICATION_HARD_DELETE = "NOTIFICATION_HARD_DELETE"

# GET /api/v1/me/notification-preferences/
NOTIFICATION_PREFERENCES_GLOBAL_GET = "NOTIFICATION_PREFERENCES_GLOBAL_GET"

# PUT /api/v1/me/notification-preferences/
NOTIFICATION_PREFERENCES_GLOBAL_PUT = "NOTIFICATION_PREFERENCES_GLOBAL_PUT"

# GET /api/v1/me/notification-preferences/event-types/
NOTIFICATION_PREFERENCES_EVENT_TYPES_GET = "NOTIFICATION_PREFERENCES_EVENT_TYPES_GET"

# PUT /api/v1/me/notification-preferences/event-types/{event_type}/
NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT = "NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT"

# Declared for services that expose admin broadcasts through user-bound flows;
# not checked by aura-notification-service views today (internals use tokens).
BROADCAST_NOTIFICATION = "BROADCAST_NOTIFICATION"
