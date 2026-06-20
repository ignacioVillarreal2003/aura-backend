"""Client for internal admin calls to aura-document-processing-service."""

import logging
import mimetypes

import requests
from django.conf import settings

from accounts.request_token import get_request_token

logger = logging.getLogger(__name__)


class DocumentProcessingServiceError(Exception):
    """Raised when the document-processing service cannot complete an admin upload."""


def _extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or 'Sin detalles adicionales.'

    return (
        payload.get('message')
        or payload.get('detail')
        or payload.get('details')
        or 'Sin detalles adicionales.'
    )


def _service_headers(actor_user, *, json_body=False):
    """Build auth headers for an admin-initiated call to document-processing.

    Forwards the caller's own Bearer token when available (set by
    BearerTokenMiddleware from the *original* incoming request); Django admin
    pages are session-authenticated, so in practice this is almost always
    unset and we fall back to service-to-service trust headers — the same
    pattern used by accounts.services.mac_client.
    """
    token = get_request_token()
    if token:
        headers = {'Authorization': token}
    else:
        headers = {
            'X-Service-Api-Key': settings.DOCUMENT_PROCESSING_SERVICE_API_KEY,
            'X-User-Id': str(actor_user.pk),
            'X-User-Email': actor_user.email or f'{actor_user.username}@local',
        }
    if json_body:
        headers['Content-Type'] = 'application/json'
    return headers


def delete_document(document_id, actor_user) -> None:
    """Soft-deletes a document in document-processing via
    DELETE /api/v1/delete-document/soft/document/{document_id}.

    Raises DocumentProcessingServiceError on any failure. A 404 (document
    already gone upstream) is treated as a successful no-op so a local
    cleanup can still proceed for records that already lost their upstream
    counterpart.
    """
    timeout_seconds = getattr(settings, 'DOCUMENT_PROCESSING_TIMEOUT_SECONDS', 300)
    url = (
        f"{settings.DOCUMENT_PROCESSING_URL.rstrip('/')}"
        f"/api/v1/delete-document/soft/document/{document_id}"
    )

    try:
        response = requests.delete(
            url,
            headers=_service_headers(actor_user),
            timeout=(10, timeout_seconds),
        )
    except requests.ConnectionError as exc:
        raise DocumentProcessingServiceError(
            'No fue posible conectar con el servicio de procesamiento de documentos. '
            'Verifica que el contenedor aura-document-processing-service esté activo.'
        ) from exc
    except requests.ReadTimeout as exc:
        raise DocumentProcessingServiceError(
            'El servicio de procesamiento de documentos tardó demasiado en responder al eliminar el documento.'
        ) from exc
    except requests.RequestException as exc:
        raise DocumentProcessingServiceError(
            'Ocurrió un error al solicitar la eliminación del documento al servicio de procesamiento.'
        ) from exc

    if response.status_code == 404:
        logger.warning(
            '[doc-processing] DELETE %s → 404 (ya no existe en el servicio de procesamiento); '
            'se continúa con la limpieza local.',
            url,
        )
        return

    if not response.ok:
        raise DocumentProcessingServiceError(
            f"El servicio de procesamiento devolvió un error ({response.status_code}) "
            f"al eliminar el documento. {_extract_error_message(response)}"
        )


def get_document(document_id, actor_user) -> dict:
    """Fetches full document metadata via GET /api/v1/document-query/document/{document_id}.

    Returns the parsed JSON body (id, status, type, category,
    processing_started_at, processing_finished_at, etc.). Raises
    DocumentProcessingServiceError on any failure — callers that only need a
    best-effort display should catch this and degrade gracefully.
    """
    timeout_seconds = getattr(settings, 'DOCUMENT_PROCESSING_TIMEOUT_SECONDS', 300)
    url = (
        f"{settings.DOCUMENT_PROCESSING_URL.rstrip('/')}"
        f"/api/v1/document-query/document/{document_id}"
    )

    try:
        response = requests.get(
            url,
            headers=_service_headers(actor_user),
            timeout=(10, min(timeout_seconds, 30)),
        )
    except requests.ConnectionError as exc:
        raise DocumentProcessingServiceError(
            'No fue posible conectar con el servicio de procesamiento de documentos.'
        ) from exc
    except requests.ReadTimeout as exc:
        raise DocumentProcessingServiceError(
            'El servicio de procesamiento de documentos tardó demasiado en responder.'
        ) from exc
    except requests.RequestException as exc:
        raise DocumentProcessingServiceError(
            'Ocurrió un error al consultar el estado del documento.'
        ) from exc

    if response.status_code == 404:
        raise DocumentProcessingServiceError('El documento no existe en el servicio de procesamiento.')

    if not response.ok:
        raise DocumentProcessingServiceError(
            f"El servicio de procesamiento devolvió un error ({response.status_code}). "
            f"{_extract_error_message(response)}"
        )

    return response.json()


def create_document_from_admin(*, raw_document, actor_user, chat_id=None, name=None, description=None):
    """Create a document in document-processing using service-to-service auth."""

    url = f"{settings.DOCUMENT_PROCESSING_URL.rstrip('/')}/api/v1/create-document"
    timeout_seconds = getattr(settings, 'DOCUMENT_PROCESSING_TIMEOUT_SECONDS', 300)
    content_type = (
        getattr(raw_document, 'content_type', None)
        or mimetypes.guess_type(raw_document.name)[0]
        or 'application/octet-stream'
    )

    files = {
        'file': (raw_document.name, raw_document, content_type),
    }
    data = {}
    if chat_id:
        data['chat_id'] = str(chat_id)
    if name:
        data['name'] = name
    if description:
        data['description'] = description

    token = get_request_token()
    if token:
        headers = {'Authorization': token}
    else:
        headers = {
            'X-Service-Api-Key': settings.DOCUMENT_PROCESSING_SERVICE_API_KEY,
            'X-User-Id': str(actor_user.pk),
            'X-User-Email': actor_user.email or f'{actor_user.username}@local',
        }

    logger.info(
        '[doc-processing] POST %s | file=%s size=%s bytes | chat_id=%s actor=%s',
        url,
        raw_document.name,
        getattr(raw_document, 'size', '?'),
        data.get('chat_id'),
        actor_user.pk,
    )

    try:
        response = requests.post(
            url,
            files=files,
            data=data,
            headers=headers,
            timeout=(10, timeout_seconds),
        )
    except requests.ConnectionError as exc:
        raise DocumentProcessingServiceError(
            'No fue posible conectar con el servicio de procesamiento de documentos. '
            'Verifica que el contenedor aura-document-processing-service esté activo en el puerto 8000.'
        ) from exc
    except requests.ReadTimeout as exc:
        raise DocumentProcessingServiceError(
            'El servicio de procesamiento de documentos tardó demasiado en responder. '
            'Si es la primera carga, es posible que esté inicializando modelos; intenta nuevamente.'
        ) from exc
    except requests.RequestException as exc:
        raise DocumentProcessingServiceError(
            'Ocurrió un error al enviar el documento al servicio de procesamiento.'
        ) from exc

    logger.info(
        '[doc-processing] response status=%s body=%s',
        response.status_code,
        response.text[:500],
    )

    if not response.ok:
        raise DocumentProcessingServiceError(
            f"El servicio de procesamiento devolvió un error ({response.status_code}). {_extract_error_message(response)}"
        )

    return response.json()
