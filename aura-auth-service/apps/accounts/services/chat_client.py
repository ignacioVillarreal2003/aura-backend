"""Cliente HTTP para aura-chat-service.

Siempre autentica con Bearer JWT. Desde el admin (que usa sesion) se genera un
token corto para el usuario, asi el chat-service sigue validando sus permisos.
"""

import logging

import requests
from django.conf import settings

from apps.accounts.request_token import get_request_token

logger = logging.getLogger(__name__)

_TIMEOUT = 10


class ChatServiceError(Exception):
    pass


class ChatClient:

    def _base_url(self):
        return getattr(settings, 'CHAT_SERVICE_URL', '').rstrip('/')

    def _headers(self, user):
        token = get_request_token()
        if not token:
            from apps.accounts.services.auth_service import issue_service_token_for_user
            token = f'Bearer {issue_service_token_for_user(user)}'
        elif not token.lower().startswith('bearer '):
            token = f'Bearer {token}'
        return {
            'Authorization': token,
            'Content-Type': 'application/json',
        }

    def _handle(self, resp):
        if resp.status_code == 401:
            raise ChatServiceError('El servicio de chat rechazó las credenciales.')
        if resp.status_code == 403:
            raise ChatServiceError('Permisos insuficientes en el servicio de chat para esta acción.')
        if resp.status_code == 404:
            raise ChatServiceError('Recurso no encontrado en el servicio de chat.')
        if resp.status_code >= 500:
            raise ChatServiceError(f'Error del servicio de chat ({resp.status_code}).')
        if not resp.ok:
            raise ChatServiceError(f'Error inesperado del servicio de chat ({resp.status_code}).')
        if resp.status_code == 204:
            return None
        try:
            return resp.json()
        except Exception:
            return None

    def _get(self, user, path, params=None):
        base = self._base_url()
        if not base:
            raise ChatServiceError('CHAT_SERVICE_URL no configurado.')
        try:
            resp = requests.get(
                f'{base}{path}',
                headers=self._headers(user),
                params=params,
                timeout=_TIMEOUT,
            )
            return self._handle(resp)
        except ChatServiceError:
            raise
        except Exception as exc:
            logger.error('Chat client GET %s failed: %s', path, exc)
            raise ChatServiceError(f'No se pudo conectar al servicio de chat: {exc}')


    def get_chats(self, user, page=1, page_size=20, search=None, ordering='-created_at'):
        """Lista todos los chats. Si falla devuelve None para que el admin use el espejo local."""
        params = {'page': page, 'page_size': page_size}
        if search:
            params['search'] = search
        if ordering:
            params['ordering'] = ordering
        try:
            data = self._get(user, '/api/v1/chats/manage/', params=params)
        except ChatServiceError as exc:
            logger.warning('ChatClient.get_chats failed, caller should fall back: %s', exc)
            return None
        if isinstance(data, dict):
            return data
        return {'results': data or [], 'count': len(data or []), 'next': None, 'previous': None}

    def get_chat(self, user, chat_id):
        """Detalle de un chat."""
        return self._get(user, f'/api/v1/chats/{chat_id}/')

    def get_chat_messages(self, user, chat_id):
        """Historial completo de mensajes de un chat (vista admin)."""
        data = self._get(user, '/api/v1/messages/manage/', params={'chat_id': chat_id})
        if isinstance(data, dict):
            return data.get('results', [])
        return data or []

    def get_chat_members(self, user, chat_id):
        """Miembros de un chat."""
        data = self._get(user, f'/api/v1/chats/{chat_id}/members/manage/')
        if isinstance(data, dict):
            return data.get('results', [])
        return data or []


    def _get_binary(self, user, path):
        """GET que devuelve una respuesta binaria en streaming (PDF/Markdown)."""
        base = self._base_url()
        if not base:
            raise ChatServiceError('CHAT_SERVICE_URL no configurado.')
        try:
            resp = requests.get(
                f'{base}{path}',
                headers=self._headers(user),
                stream=True,
                timeout=(10, 60),
            )
        except Exception as exc:
            logger.error('Chat client GET(binary) %s failed: %s', path, exc)
            raise ChatServiceError(f'No se pudo conectar al servicio de chat: {exc}')

        if resp.ok:
            return resp
        status_code = resp.status_code
        resp.close()
        if status_code == 401:
            raise ChatServiceError('El servicio de chat rechazó las credenciales.')
        if status_code == 403:
            raise ChatServiceError('Permisos insuficientes en el servicio de chat para esta acción.')
        if status_code == 404:
            raise ChatServiceError('Recurso no encontrado en el servicio de chat.')
        raise ChatServiceError(f'Error inesperado del servicio de chat ({status_code}).')

    def export_chat(self, user, chat_id, fmt):
        """Exporta un chat en PDF o Markdown."""
        suffix = 'pdf' if fmt == 'pdf' else 'markdown'
        return self._get_binary(user, f'/api/v1/chats/{chat_id}/manage/export/{suffix}/')


chat_client = ChatClient()
