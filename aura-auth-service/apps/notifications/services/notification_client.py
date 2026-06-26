"""Client for internal calls to aura-notification-service.

The notification service exposes a single internal endpoint for producers:
``POST /api/v1/internal/events/`` authenticated with the ``X-Internal-Token``
header. Producers send a semantic ``event_type`` plus ``recipient_ids`` and a
``context`` dict; the service resolves templates, channels and user
preferences on its side.
"""

import logging
import threading
from urllib.parse import urlsplit, urlunsplit

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class NotificationServiceError(Exception):
    """Raised when a synchronous notification service call fails (admin flows)."""


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


def _build_payload(*, event_type, recipient_ids, actor_id=None, actor_name='', context=None, link_url=None) -> dict:
    payload = {
        'event_type': event_type,
        'recipient_ids': [int(item) for item in recipient_ids],
    }
    if actor_id is not None:
        payload['actor_id'] = int(actor_id)
    if actor_name:
        payload['actor_name'] = str(actor_name)
    if context:
        payload['context'] = context
    if link_url:
        payload['link_url'] = link_url
    return payload


def emit_event(*, event_type, recipient_ids, actor_id=None, actor_name='', context=None, link_url=None) -> dict:
    """
    Emit a notification event synchronously.

    Returns the service response body (``created``, ``skipped``, ``pending_email``,
    ``outcomes``). Raises NotificationServiceError on any failure — use this for
    admin flows where the caller needs feedback.
    """
    base_url = _normalize_base_url(settings.NOTIFICATION_SERVICE_URL)
    payload = _build_payload(
        event_type=event_type,
        recipient_ids=recipient_ids,
        actor_id=actor_id,
        actor_name=actor_name,
        context=context,
        link_url=link_url,
    )
    url = f"{base_url}/api/v1/internal/events/"

    try:
        response = requests.post(
            url,
            json=payload,
            headers={'X-Internal-Token': settings.NOTIFICATION_INTERNAL_API_TOKEN},
            timeout=(4, settings.NOTIFICATION_SERVICE_TIMEOUT_SECONDS),
            allow_redirects=False,
        )
    except requests.Timeout as exc:
        raise NotificationServiceError(
            'El servicio de notificaciones no respondio a tiempo. Verifica que este activo.'
        ) from exc
    except requests.ConnectionError as exc:
        raise NotificationServiceError(
            'No se pudo conectar con el servicio de notificaciones. Verifica que este activo.'
        ) from exc
    except requests.RequestException as exc:
        raise NotificationServiceError('Ocurrio un error al contactar el servicio de notificaciones.') from exc

    if response.status_code in (301, 302, 307, 308):
        raise NotificationServiceError(
            'El servicio de notificaciones devolvió una redirección inesperada. Revisa su configuración HTTPS/HTTP.'
        )
    if not response.ok:
        raise NotificationServiceError(
            f'El servicio de notificaciones devolvió {response.status_code}. {_extract_error(response)}'
        )

    return response.json()


def emit_event_async(*, event_type, recipient_ids, actor_id=None, actor_name='', context=None, link_url=None) -> None:
    """
    Fire-and-forget event emission for request-path flows (login, password change).

    Never raises: a notification failure must not break authentication. Errors
    are logged only.
    """

    def _send():
        try:
            emit_event(
                event_type=event_type,
                recipient_ids=recipient_ids,
                actor_id=actor_id,
                actor_name=actor_name,
                context=context,
                link_url=link_url,
            )
        except NotificationServiceError as exc:
            logger.warning("Failed to emit notification event '%s': %s", event_type, exc)
        except Exception:
            logger.exception("Unexpected error emitting notification event '%s'.", event_type)

    threading.Thread(target=_send, name=f'notif-{event_type}', daemon=True).start()


def create_notifications_from_admin(*, receiver_ids, message, target_scope, target_label, actor_user_id, actor_name=''):
    """
    Send an admin broadcast through the notification service.

    ``target_scope``/``target_label`` are kept inside ``context`` so the admin
    panel can keep splitting individual vs group sends when reading the
    ``data`` JSONB column back. Raises NotificationServiceError on failure.
    """
    context = {
        'message': message,
        'target_scope': target_scope,
        'target_label': target_label,
    }
    return emit_event(
        event_type='admin.broadcast',
        recipient_ids=receiver_ids,
        actor_id=actor_user_id,
        actor_name=actor_name,
        context=context,
    )
