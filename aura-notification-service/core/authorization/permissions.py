# Notification-service application permissions.
#
# These names are issued by the central authentication service inside the
# user JWT payload (`permissions` claim). Endpoints check them through
# `AccessControl.require_permissions(user, frozenset({...}))`.

LIST_NOTIFICATIONS = "LIST_NOTIFICATIONS"
READ_NOTIFICATION = "READ_NOTIFICATION"
UPDATE_NOTIFICATION = "UPDATE_NOTIFICATION"
DELETE_NOTIFICATION = "DELETE_NOTIFICATION"

MANAGE_NOTIFICATION_PREFERENCES = "MANAGE_NOTIFICATION_PREFERENCES"

BROADCAST_NOTIFICATION = "BROADCAST_NOTIFICATION"
