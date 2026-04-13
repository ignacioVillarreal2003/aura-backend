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


def _serialize_id(value):
    """Serialize UUID/int ids safely for JSON payloads."""

    return str(value) if value is not None else None


def _candidate_base_urls(configured_url: str) -> list[str]:
    """Return candidate base URLs with localhost port fallback for dev."""

    base = _normalize_base_url(configured_url)
    parsed = urlsplit(base)
    candidates = [base]

    if parsed.hostname in {'localhost', '127.0.0.1'}:
        if parsed.port == 8004:
            candidates.append(base.replace(':8004', ':8005'))
        elif parsed.port == 8005:
            candidates.append(base.replace(':8005', ':8004'))

    # Keep order but remove duplicates.
    seen = set()
    ordered = []
    for item in candidates:
        if item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def create_notifications_from_admin(*, receiver_ids, message, notification_type, target_scope, target_label, actor_user_id):
    """
    Create notifications by calling the trusted internal endpoint of aura-notification-service.
    Raises requests.HTTPError on non-success responses.
    """
    base_urls = _candidate_base_urls(settings.NOTIFICATION_SERVICE_URL)
    payload = {
        'receiver_ids': [_serialize_id(item) for item in receiver_ids],
        'message': message,
        'type': notification_type,
        'target_scope': target_scope,
        'target_label': target_label,
        'actor_user_id': _serialize_id(actor_user_id),
    }

    request_kwargs = {
        'json': payload,
        'headers': {'X-Internal-Token': settings.NOTIFICATION_INTERNAL_API_TOKEN},
        'timeout': (4, settings.NOTIFICATION_SERVICE_TIMEOUT_SECONDS),
        'allow_redirects': False,
    }

    last_timeout_exc = None
    last_connection_exc = None
    last_response = None

    for base_url in base_urls:
        url = f"{base_url}/api/internal/notifications/admin-create/"
        try:
            response = requests.post(url, **request_kwargs)

            # Retry once when service redirects HTTP/HTTPS or canonical path.
            if response.status_code in (301, 302, 307, 308):
                redirect_url = response.headers.get('Location')
                if redirect_url:
                    if redirect_url.startswith('/'):
                        parsed = urlsplit(url)
                        redirect_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                    response = requests.post(redirect_url, **request_kwargs)

            if response.ok:
                return response.json()

            last_response = response
        except requests.Timeout as exc:
            last_timeout_exc = exc
            continue
        except requests.ConnectionError as exc:
            last_connection_exc = exc
            continue
        except requests.RequestException as exc:
            raise NotificationServiceError('Ocurrio un error al contactar el servicio de notificaciones.') from exc

    if last_response is None:
        if last_timeout_exc is not None:
            raise NotificationServiceError(
                'El servicio de notificaciones no respondio a tiempo. Verifica que este activo en 8004.'
            ) from last_timeout_exc
        if last_connection_exc is not None:
            raise NotificationServiceError(
                'No se pudo conectar con el servicio de notificaciones. Verifica que este activo en 8004.'
            ) from last_connection_exc
        raise NotificationServiceError('No fue posible contactar al servicio de notificaciones.')

    response = last_response

    if response.status_code in (301, 302, 307, 308):
        raise NotificationServiceError(
            'El servicio de notificaciones devolvió una redirección inesperada. Revisa su configuración HTTPS/HTTP.'
        )
    if not response.ok:
        raise NotificationServiceError(
            f'El servicio de notificaciones devolvió {response.status_code}. {_extract_error(response)}'
        )

    return response.json()
