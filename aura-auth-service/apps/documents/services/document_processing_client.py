"""Client for internal admin calls to aura-document-processing-service.

Authentication model: every call is authenticated with a Bearer JWT obtained
via ``accounts.services.auth_service.get_outbound_authorization`` — it forwards
the caller's own token when present (rare in the session-authenticated Django
admin) and otherwise mints a short-lived JWT for the acting user. The
downstream service validates it against this service's ``GET /auth/validate``
and enforces the user's REAL RBAC permissions, so the ``*_MANAGE`` permissions
seeded by ``manage.py seed_service_manage_permissions`` must be present for
these calls to succeed.

The document-processing auth middleware accepts ONLY Bearer tokens (no
X-Service-Api-Key trust headers), which is why this client does not use the
service-trust header pattern.
"""

import logging
import mimetypes

import requests
from django.conf import settings

from apps.accounts.services.auth_service import get_outbound_authorization

logger = logging.getLogger(__name__)

# Connect / read timeout split. Read timeout falls back to the configured
# processing timeout (uploads/reprocess can be slow); cheap GETs cap it lower.
_CONNECT_TIMEOUT = 10


class DocumentProcessingServiceError(Exception):
    """Raised when the document-processing service cannot complete a call."""


# Bulk operation -> URL segment under /api/v1/.
_BULK_SEGMENTS = {
    'reprocess': 'document-reprocess',
    'reembed': 'document-reembed',
    'enrich': 'document-enrich',
    'graph_extract': 'graph/extraction',
}


def _base_url() -> str:
    base = getattr(settings, 'DOCUMENT_PROCESSING_URL', '') or ''
    return base.rstrip('/')


def _read_timeout(cap: int | None = None) -> int:
    value = getattr(settings, 'DOCUMENT_PROCESSING_TIMEOUT_SECONDS', 300)
    if cap is not None:
        return min(value, cap)
    return value


def _extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or 'Sin detalles adicionales.'

    if isinstance(payload, dict):
        return (
            payload.get('message')
            or payload.get('detail')
            or payload.get('details')
            or 'Sin detalles adicionales.'
        )
    return 'Sin detalles adicionales.'


def _auth_headers(actor_user, *, json_body: bool = False) -> dict:
    """Build the Authorization header for an admin-initiated call."""
    authorization = get_outbound_authorization(actor_user)
    if not authorization:
        raise DocumentProcessingServiceError(
            'No hay credenciales para autenticar la llamada al servicio de procesamiento.'
        )
    headers = {'Authorization': authorization}
    if json_body:
        headers['Content-Type'] = 'application/json'
    return headers


def _handle_error(response: requests.Response) -> None:
    """Raise DocumentProcessingServiceError for non-OK responses (except 404,
    which several callers want to special-case before this is reached)."""
    if response.status_code in (401, 403):
        raise DocumentProcessingServiceError(
            'Permisos insuficientes en el servicio de procesamiento para esta acción.'
        )
    if response.status_code == 409:
        raise DocumentProcessingServiceError(
            'Ya hay una operación masiva del mismo tipo en curso. Espera a que termine o detenla.'
        )
    if response.status_code >= 500:
        raise DocumentProcessingServiceError(
            f'El servicio de procesamiento devolvió un error ({response.status_code}). '
            f'{_extract_error_message(response)}'
        )
    if not response.ok:
        raise DocumentProcessingServiceError(
            f'El servicio de procesamiento devolvió un error ({response.status_code}). '
            f'{_extract_error_message(response)}'
        )


def _request(method: str, path: str, actor_user, *, json_payload=None, timeout_cap=None):
    """Perform a JSON request and return the parsed body (or None for 204)."""
    base = _base_url()
    if not base:
        raise DocumentProcessingServiceError('DOCUMENT_PROCESSING_URL no configurado.')
    url = f'{base}{path}'
    try:
        response = requests.request(
            method,
            url,
            headers=_auth_headers(actor_user, json_body=json_payload is not None),
            json=json_payload,
            timeout=(_CONNECT_TIMEOUT, _read_timeout(timeout_cap)),
        )
    except DocumentProcessingServiceError:
        raise
    except requests.ConnectionError as exc:
        raise DocumentProcessingServiceError(
            'No fue posible conectar con el servicio de procesamiento de documentos. '
            'Verifica que el contenedor aura-document-processing-service esté activo.'
        ) from exc
    except requests.ReadTimeout as exc:
        raise DocumentProcessingServiceError(
            'El servicio de procesamiento de documentos tardó demasiado en responder.'
        ) from exc
    except requests.RequestException as exc:
        logger.error('[doc-processing] %s %s failed: %s', method, path, exc)
        raise DocumentProcessingServiceError(
            'Ocurrió un error al comunicarse con el servicio de procesamiento.'
        ) from exc

    _handle_error(response)
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return None


# ── Create (unchanged contract; used by documents/admin.py add flow) ──────────

def create_document_from_admin(
    *, raw_document, actor_user, chat_id=None, name=None,
    enrich=False, graph_extract=False,
):
    """Create a document in document-processing using the acting user's JWT.

    Description is intentionally NOT accepted here: it is generated automatically
    downstream (enrichment). ``enrich`` (LLM fragment enrichment) and
    ``graph_extract`` (knowledge-graph extraction) map to the matching flags on
    the service's CreateDocumentRequest; both default to False (same as the
    service)."""
    url = f"{_base_url()}/api/v1/create-document"
    content_type = (
        getattr(raw_document, 'content_type', None)
        or mimetypes.guess_type(raw_document.name)[0]
        or 'application/octet-stream'
    )

    files = {'file': (raw_document.name, raw_document, content_type)}
    data = {
        'enrich': 'true' if enrich else 'false',
        'graph_extract': 'true' if graph_extract else 'false',
    }
    if chat_id:
        data['chat_id'] = str(chat_id)
    if name:
        data['name'] = name

    # Multipart upload: do not set Content-Type (requests sets the boundary).
    headers = _auth_headers(actor_user)

    logger.info(
        '[doc-processing] POST %s | file=%s size=%s bytes | chat_id=%s enrich=%s graph_extract=%s actor=%s',
        url, raw_document.name, getattr(raw_document, 'size', '?'), data.get('chat_id'),
        data['enrich'], data['graph_extract'], actor_user.pk,
    )

    try:
        response = requests.post(
            url, files=files, data=data, headers=headers,
            timeout=(_CONNECT_TIMEOUT, _read_timeout()),
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

    logger.info('[doc-processing] response status=%s body=%s', response.status_code, response.text[:500])
    _handle_error(response)
    return response.json()


# ── Bulk create (unchanged contract; used by documents/admin.py bulk add flow) ─

def bulk_create_documents_from_admin(
    *, raw_documents, actor_user, chat_id=None,
    enrich=False, graph_extract=False,
):
    """Create several documents in one call to document-processing.

    Mirrors ``create_document_from_admin`` but sends every file under the same
    ``file`` multipart field (FastAPI binds the repeated field to a list). The
    same processing options apply to the whole batch; no per-file name is sent
    (each document keeps its filename). Returns BulkCreateDocumentResponse
    {total, created, failed, items}."""
    url = f"{_base_url()}/api/v1/bulk-create-document"

    files = []
    for raw_document in raw_documents:
        content_type = (
            getattr(raw_document, 'content_type', None)
            or mimetypes.guess_type(raw_document.name)[0]
            or 'application/octet-stream'
        )
        files.append(('files', (raw_document.name, raw_document, content_type)))

    data = {
        'enrich': 'true' if enrich else 'false',
        'graph_extract': 'true' if graph_extract else 'false',
    }
    if chat_id:
        data['chat_id'] = str(chat_id)

    # Multipart upload: do not set Content-Type (requests sets the boundary).
    headers = _auth_headers(actor_user)

    logger.info(
        '[doc-processing] POST %s | files=%s | chat_id=%s enrich=%s graph_extract=%s actor=%s',
        url, [getattr(f, 'name', '?') for f in raw_documents], data.get('chat_id'),
        data['enrich'], data['graph_extract'], actor_user.pk,
    )

    try:
        response = requests.post(
            url, files=files, data=data, headers=headers,
            timeout=(_CONNECT_TIMEOUT, _read_timeout()),
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
            'Ocurrió un error al enviar los documentos al servicio de procesamiento.'
        ) from exc

    logger.info('[doc-processing] response status=%s body=%s', response.status_code, response.text[:500])
    _handle_error(response)
    return response.json()


# ── Read (manage) ─────────────────────────────────────────────────────────────

def get_document(document_id, actor_user) -> dict:
    """GET /api/v1/document-query/manage/document/{id} — full metadata.

    Raises DocumentProcessingServiceError (incl. on 404)."""
    base = _base_url()
    if not base:
        raise DocumentProcessingServiceError('DOCUMENT_PROCESSING_URL no configurado.')
    url = f"{base}/api/v1/document-query/manage/document/{document_id}"
    try:
        response = requests.get(
            url, headers=_auth_headers(actor_user),
            timeout=(_CONNECT_TIMEOUT, _read_timeout(cap=30)),
        )
    except DocumentProcessingServiceError:
        raise
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
    _handle_error(response)
    return response.json()


# ── Update (manage) ───────────────────────────────────────────────────────────

def update_document(document_id, actor_user, *, name=None, description=None, category=None) -> dict:
    """PATCH /api/v1/update-document/manage/document/{id}.

    Sends only provided fields (PATCH semantics; at least one required).
    ``description`` may be passed as '' to clear it (sent as null)."""
    payload = {}
    if name is not None:
        payload['name'] = name
    if description is not None:
        payload['description'] = description or None
    if category is not None:
        payload['category'] = category
    if not payload:
        raise DocumentProcessingServiceError('No hay campos para actualizar.')

    return _request(
        'PATCH',
        f"/api/v1/update-document/manage/document/{document_id}",
        actor_user,
        json_payload=payload,
        timeout_cap=30,
    )


# ── Soft delete (manage) ──────────────────────────────────────────────────────

def delete_document(document_id, actor_user) -> None:
    """DELETE /api/v1/delete-document/manage/soft/document/{id}.

    A 404 (already gone upstream) is treated as a successful no-op so a local
    cleanup can still proceed."""
    base = _base_url()
    if not base:
        raise DocumentProcessingServiceError('DOCUMENT_PROCESSING_URL no configurado.')
    url = f"{base}/api/v1/delete-document/manage/soft/document/{document_id}"
    try:
        response = requests.delete(
            url, headers=_auth_headers(actor_user),
            timeout=(_CONNECT_TIMEOUT, _read_timeout()),
        )
    except DocumentProcessingServiceError:
        raise
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
            '[doc-processing] DELETE %s -> 404 (ya no existe); se continúa con la limpieza local.', url,
        )
        return
    _handle_error(response)


# ── Restore (manage) ──────────────────────────────────────────────────────────

def restore_document(document_id, actor_user) -> dict:
    """POST /api/v1/restore-document/manage/document/{id}."""
    return _request(
        'POST',
        f"/api/v1/restore-document/manage/document/{document_id}",
        actor_user,
        timeout_cap=60,
    )


# ── Download (manage) — streaming ─────────────────────────────────────────────

def download_document(document_id, actor_user) -> requests.Response:
    """GET /api/v1/document-download/manage/document/{id}/download.

    Returns a streaming ``requests.Response`` (caller must iterate and close).
    Raises DocumentProcessingServiceError on failure."""
    base = _base_url()
    if not base:
        raise DocumentProcessingServiceError('DOCUMENT_PROCESSING_URL no configurado.')
    url = f"{base}/api/v1/document-download/manage/document/{document_id}/download"
    try:
        response = requests.get(
            url, headers=_auth_headers(actor_user), stream=True,
            timeout=(_CONNECT_TIMEOUT, _read_timeout()),
        )
    except DocumentProcessingServiceError:
        raise
    except requests.ConnectionError as exc:
        raise DocumentProcessingServiceError(
            'No fue posible conectar con el servicio de procesamiento de documentos.'
        ) from exc
    except requests.RequestException as exc:
        raise DocumentProcessingServiceError(
            'Ocurrió un error al descargar el documento.'
        ) from exc

    if response.status_code == 404:
        response.close()
        raise DocumentProcessingServiceError('El documento no existe en el servicio de procesamiento.')
    if not response.ok:
        try:
            _handle_error(response)
        finally:
            response.close()
    return response


# ── Bulk operations (manage) ──────────────────────────────────────────────────

def _selector(document_ids=None, all_documents=False) -> dict:
    if all_documents:
        return {'all_documents': True}
    ids = [int(i) for i in (document_ids or [])]
    if not ids:
        raise DocumentProcessingServiceError('No se seleccionaron documentos.')
    return {'document_ids': ids}


def start_bulk_job(
    operation, actor_user, *, document_ids=None, all_documents=False,
    prefer_docling=True, enrich=False, graph_extract=False,
) -> dict:
    """POST /api/v1/{segment}/manage — encola una operación masiva.

    Returns BulkStartResponse {job_id, operation, total, queued}."""
    segment = _BULK_SEGMENTS.get(operation)
    if segment is None:
        raise DocumentProcessingServiceError(f'Operación masiva desconocida: {operation}')

    payload = {'selector': _selector(document_ids, all_documents)}
    if operation == 'reprocess':
        payload['prefer_docling'] = prefer_docling
        payload['enrich'] = enrich
        payload['graph_extract'] = graph_extract

    return _request('POST', f"/api/v1/{segment}/manage", actor_user, json_payload=payload, timeout_cap=60)


def get_bulk_job_status(operation, actor_user) -> dict:
    """GET /api/v1/{segment}/manage/status — BulkJobStatusResponse."""
    segment = _BULK_SEGMENTS.get(operation)
    if segment is None:
        raise DocumentProcessingServiceError(f'Operación masiva desconocida: {operation}')
    return _request('GET', f"/api/v1/{segment}/manage/status", actor_user, timeout_cap=30)


def stop_bulk_job(operation, actor_user) -> dict:
    """DELETE /api/v1/{segment}/manage/stop — BulkJobStatusResponse."""
    segment = _BULK_SEGMENTS.get(operation)
    if segment is None:
        raise DocumentProcessingServiceError(f'Operación masiva desconocida: {operation}')
    return _request('DELETE', f"/api/v1/{segment}/manage/stop", actor_user, timeout_cap=30)


# ── Graph stats (manage) ──────────────────────────────────────────────────────

def get_graph_stats(actor_user) -> dict:
    """GET /api/v1/graph/stats/manage — GraphStatsResponse."""
    return _request('GET', "/api/v1/graph/stats/manage", actor_user, timeout_cap=30)
