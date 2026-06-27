"""Cliente HTTP para el servicio de colecciones de documentos (MAC)."""

import logging

import requests
from django.conf import settings

from apps.accounts.services.auth_service import get_outbound_authorization

logger = logging.getLogger(__name__)

_TIMEOUT = 10


class MacServiceError(Exception):
    pass


class MacServiceClient:

    def _base_url(self):
        return getattr(settings, 'DOC_COLLECTION_SERVICE_URL', '').rstrip('/')

    def _headers(self, user):
        if user is None:
            return {
                'X-Service-Api-Key': settings.SERVICE_API_KEY,
                'Content-Type': 'application/json',
            }
        authorization = get_outbound_authorization(user)
        if not authorization:
            raise MacServiceError('No hay credenciales para autenticar la llamada al servicio MAC.')
        return {
            'Authorization': authorization,
            'Content-Type': 'application/json',
        }

    def _handle(self, resp, method=''):
        if resp.status_code == 404:
            raise MacServiceError('Recurso no encontrado.')
        if resp.status_code == 409:
            if method == 'DELETE':
                raise MacServiceError(
                    'No se puede eliminar: el recurso tiene usuarios o documentos asignados. '
                    'Quítalos primero antes de eliminar.'
                )
            raise MacServiceError('Conflicto: el recurso ya existe.')
        if resp.status_code == 400:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            raise MacServiceError(f'Error de validación: {detail}')
        if resp.status_code >= 500:
            raise MacServiceError(f'Error del servidor MAC ({resp.status_code}).')
        if not resp.ok:
            raise MacServiceError(f'Error inesperado ({resp.status_code}).')
        if resp.status_code == 204:
            return None
        try:
            return resp.json()
        except Exception:
            return None

    def _get(self, user, path, params=None):
        base = self._base_url()
        if not base:
            return []
        try:
            resp = requests.get(
                f'{base}{path}',
                headers=self._headers(user),
                params=params,
                timeout=_TIMEOUT,
            )
            return self._handle(resp)
        except MacServiceError:
            raise
        except Exception as exc:
            logger.error('MAC client GET %s failed: %s', path, exc)
            raise MacServiceError(f'No se pudo conectar al servicio MAC: {exc}')

    def _post(self, user, path, data):
        base = self._base_url()
        if not base:
            raise MacServiceError('DOC_COLLECTION_SERVICE_URL no configurado.')
        try:
            resp = requests.post(
                f'{base}{path}',
                headers=self._headers(user),
                json=data,
                timeout=_TIMEOUT,
            )
            return self._handle(resp)
        except MacServiceError:
            raise
        except Exception as exc:
            logger.error('MAC client POST %s failed: %s', path, exc)
            raise MacServiceError(f'No se pudo conectar al servicio MAC: {exc}')

    def _patch(self, user, path, data):
        base = self._base_url()
        if not base:
            raise MacServiceError('DOC_COLLECTION_SERVICE_URL no configurado.')
        try:
            resp = requests.patch(
                f'{base}{path}',
                headers=self._headers(user),
                json=data,
                timeout=_TIMEOUT,
            )
            return self._handle(resp)
        except MacServiceError:
            raise
        except Exception as exc:
            logger.error('MAC client PATCH %s failed: %s', path, exc)
            raise MacServiceError(f'No se pudo conectar al servicio MAC: {exc}')

    def _put(self, user, path, data):
        base = self._base_url()
        if not base:
            raise MacServiceError('DOC_COLLECTION_SERVICE_URL no configurado.')
        try:
            resp = requests.put(
                f'{base}{path}',
                headers=self._headers(user),
                json=data,
                timeout=_TIMEOUT,
            )
            return self._handle(resp)
        except MacServiceError:
            raise
        except Exception as exc:
            logger.error('MAC client PUT %s failed: %s', path, exc)
            raise MacServiceError(f'No se pudo conectar al servicio MAC: {exc}')

    def _delete(self, user, path):
        base = self._base_url()
        if not base:
            raise MacServiceError('DOC_COLLECTION_SERVICE_URL no configurado.')
        try:
            resp = requests.delete(
                f'{base}{path}',
                headers=self._headers(user),
                timeout=_TIMEOUT,
            )
            return self._handle(resp, method='DELETE')
        except MacServiceError:
            raise
        except Exception as exc:
            logger.error('MAC client DELETE %s failed: %s', path, exc)
            raise MacServiceError(f'No se pudo conectar al servicio MAC: {exc}')


    def list_classification_levels(self, user):
        data = self._get(user, '/api/v1/classification-levels/')
        if isinstance(data, dict):
            return data.get('results', data.get('data', []))
        return data or []

    def create_classification_level(self, user, name, rank, description=''):
        return self._post(user, '/api/v1/classification-levels/', {'name': name, 'rank': rank, 'description': description})

    def get_classification_level(self, user, level_id):
        return self._get(user, f'/api/v1/classification-levels/{level_id}/')

    def update_classification_level(self, user, level_id, **kwargs):
        return self._patch(user, f'/api/v1/classification-levels/{level_id}/', kwargs)

    def delete_classification_level(self, user, level_id):
        return self._delete(user, f'/api/v1/classification-levels/{level_id}/')


    def list_compartments(self, user):
        data = self._get(user, '/api/v1/compartments/')
        if isinstance(data, dict):
            return data.get('results', data.get('data', []))
        return data or []

    def create_compartment(self, user, name, description=''):
        return self._post(user, '/api/v1/compartments/', {'name': name, 'description': description})

    def get_compartment(self, user, compartment_id):
        return self._get(user, f'/api/v1/compartments/{compartment_id}/')

    def update_compartment(self, user, compartment_id, **kwargs):
        return self._patch(user, f'/api/v1/compartments/{compartment_id}/', kwargs)

    def delete_compartment(self, user, compartment_id):
        return self._delete(user, f'/api/v1/compartments/{compartment_id}/')


    def list_document_collections(self, user):
        data = self._get(user, '/api/v1/document-collections/')
        if isinstance(data, dict):
            return data.get('results', data.get('data', []))
        return data or []

    def create_document_collection(self, user, name, classification_level_id=None, compartment_ids=None):
        payload = {'name': name}
        if classification_level_id is not None:
            payload['classification_level_id'] = classification_level_id
        if compartment_ids:
            payload['compartment_ids'] = compartment_ids
        return self._post(user, '/api/v1/document-collections/', payload)

    def get_document_collection(self, user, collection_id):
        return self._get(user, f'/api/v1/document-collections/{collection_id}/')

    def update_document_collection(self, user, collection_id, **kwargs):
        return self._patch(user, f'/api/v1/document-collections/{collection_id}/', kwargs)

    def delete_document_collection(self, user, collection_id):
        return self._delete(user, f'/api/v1/document-collections/{collection_id}/')

    def list_collection_documents(self, user, collection_id):
        data = self._get(user, f'/api/v1/document-collections/{collection_id}/documents/')
        if isinstance(data, dict):
            return data.get('results', [])
        return data or []

    def add_document_to_collection(self, user, collection_id, document_id):
        return self._post(
            user, f'/api/v1/document-collections/{collection_id}/documents/',
            {'document_id': document_id},
        )

    def remove_document_from_collection(self, user, collection_id, doc_id):
        return self._delete(
            user, f'/api/v1/document-collections/{collection_id}/documents/{doc_id}/'
        )


    def get_user_authorization(self, user, target_user_id):
        return self._get(user, f'/api/v1/user-authorizations/{target_user_id}/')

    def set_user_clearance(self, user, target_user_id, classification_level_id):
        return self._put(
            user, f'/api/v1/user-authorizations/{target_user_id}/clearance/',
            {'classification_level_id': classification_level_id},
        )

    def delete_user_clearance(self, user, target_user_id):
        return self._delete(user, f'/api/v1/user-authorizations/{target_user_id}/clearance/')

    def list_user_compartments(self, user, target_user_id):
        data = self._get(user, f'/api/v1/user-authorizations/{target_user_id}/compartments/')
        if isinstance(data, dict):
            return data.get('results', [])
        return data or []

    def add_user_compartment(self, user, target_user_id, compartment_id):
        return self._post(
            user, f'/api/v1/user-authorizations/{target_user_id}/compartments/',
            {'compartment_id': compartment_id},
        )

    def remove_user_compartment(self, user, target_user_id, compartment_id):
        return self._delete(
            user, f'/api/v1/user-authorizations/{target_user_id}/compartments/{compartment_id}/'
        )


mac_client = MacServiceClient()
