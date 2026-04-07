"""Client for internal calls to aura-notification-service."""

from urllib.parse import urlsplit, urlunsplit

import requests
from django.conf import settings


class NotificationServiceError(Exception):
    """Raised when notification service call fails for admin flows."""


def _normalize_base_url(url: str) -> str:
    """Force plain HTTP for local endpoints to avoid broken TLS redirects in dev."""

    parsed = urlsplit(url.rstrip('/'))
    if parsed.hostname in {'localhost', '127.0.0.1'} and parsed.scheme == 'https':
        return urlunsplit(('http', parsed.netloc, parsed.path, parsed.query, parsed.fragment)).rstrip('/')
    return url.rstrip('/')


def _extract_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or 'Sin detalles adicionales.'
    return payload.get('detail') or payload.get('message') or payload.get('error') or 'Sin detalles adicionales.'


def create_notifications_from_admin(*, receiver_ids, message, notification_type, target_scope, target_label, actor_user_id):
    """
    Create notifications by calling the trusted internal endpoint of aura-notification-service.
    Raises requests.HTTPError on non-success responses.
    """
    base_url = _normalize_base_url(settings.NOTIFICATION_SERVICE_URL)
    url = f"{base_url}/api/internal/notifications/admin-create/"
    payload = {
        'receiver_ids': receiver_ids,
        'message': message,
        'type': notification_type,
        'target_scope': target_scope,
        'target_label': target_label,
        'actor_user_id': actor_user_id,
    }
    try:
        response = requests.post(
            url,
            json=payload,
            headers={'X-Internal-Token': settings.NOTIFICATION_INTERNAL_API_TOKEN},
            timeout=(10, settings.NOTIFICATION_SERVICE_TIMEOUT_SECONDS),
            allow_redirects=False,
        )
    except requests.ReadTimeout as exc:
        raise NotificationServiceError(
            'El servicio de notificaciones tardó demasiado en responder. Intenta nuevamente en unos segundos.'
        ) from exc
    except requests.ConnectionError as exc:
        raise NotificationServiceError(
            'No se pudo conectar con el servicio de notificaciones. Verifica que el contenedor esté activo en el puerto 8002.'
        ) from exc
    except requests.RequestException as exc:
        raise NotificationServiceError('Ocurrió un error al contactar el servicio de notificaciones.') from exc

    if response.status_code in (301, 302, 307, 308):
        raise NotificationServiceError(
            'El servicio de notificaciones devolvió una redirección inesperada. Revisa su configuración HTTPS/HTTP.'
        )
    if not response.ok:
        raise NotificationServiceError(
            f'El servicio de notificaciones devolvió {response.status_code}. {_extract_error(response)}'
        )

    return response.json()
