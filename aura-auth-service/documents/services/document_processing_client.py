"""Client for internal admin calls to aura-document-processing-service."""

import logging
import mimetypes

import requests
from django.conf import settings

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


def create_document_from_admin(*, raw_document, chat_id, actor_user):
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

    headers = {
        'X-Service-Api-Key': settings.DOCUMENT_PROCESSING_SERVICE_API_KEY,
        'X-User-Id': str(actor_user.pk),
        'X-User-Email': actor_user.email or f'{actor_user.username}@local',
        'X-User-Permissions': 'INGEST_DOCUMENT',
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
