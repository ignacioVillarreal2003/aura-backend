"""Client for internal calls to aura-notification-service."""

import requests
from django.conf import settings


def create_notifications_from_admin(*, receiver_ids, message, notification_type, target_scope, target_label, actor_user_id):
    """
    Create notifications by calling the trusted internal endpoint of aura-notification-service.
    Raises requests.HTTPError on non-success responses.
    """
    url = f"{settings.NOTIFICATION_SERVICE_URL}/api/internal/notifications/admin-create/"
    payload = {
        'receiver_ids': receiver_ids,
        'message': message,
        'type': notification_type,
        'target_scope': target_scope,
        'target_label': target_label,
        'actor_user_id': actor_user_id,
    }
    response = requests.post(
        url,
        json=payload,
        headers={'X-Internal-Token': settings.NOTIFICATION_INTERNAL_API_TOKEN},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
