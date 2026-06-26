"""HTTP client for aura-chat-service.

Auth model differs from the other clients in this package (mac_client.py,
document_processing_client.py): chat-service has **no** X-Service-Api-Key /
X-User-Id trust-header fallback. Every request there is authenticated
exclusively via ``Authorization: Bearer <JWT>``, which chat-service validates
by calling back to *this* service's own ``GET /auth/validate`` (cached in
Redis) — see aura-chat-service/core/authentication/authentication_provider.py.

Django admin pages are session-cookie-authenticated, so there is normally no
Bearer token on the inbound request to forward via
``accounts.request_token.get_request_token()`` (that ContextVar is only ever
populated when the *original* request itself carried one). Instead, we mint a
short-lived access token for the acting admin user via
``accounts.services.auth_service.issue_service_token_for_user`` and send
that. chat-service then resolves the user's *real* roles/permissions through
the normal validation path, so ``MANAGE_CHATS`` / ``GET_CHAT`` / etc. are
genuinely enforced rather than bypassed — the admin user must actually hold
the relevant permission for these calls to succeed, same as any other client
of chat-service's API.
"""

import logging

import requests
from django.conf import settings

from accounts.request_token import get_request_token

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
            from accounts.services.auth_service import issue_service_token_for_user
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

    # ── Chats ────────────────────────────────────────────────────────────────

    def get_chats(self, user, page=1, page_size=20, search=None, ordering='-created_at'):
        """GET /api/v1/chats/manage/ — every chat in the system (MANAGE_CHATS).

        Response shape: {count, next, previous, results: [...]}. Each result
        has id, name, tags, is_locked, last_message_at, created_by,
        created_at, member_count (see ChatManageListResponse in
        aura-chat-service — there is no last-message-preview field).

        Unlike every other method on this client, get_chats() does NOT
        raise ChatServiceError — it logs and returns None. This is a
        deliberate, scoped exception to this client's normal "raise and let
        the caller decide how to degrade" convention: the *list* admin view
        (accounts/admin_parts/chat_management_admin.py) falls back to the
        local aura_db mirror when this returns None. The detail-view
        methods below keep raising, since there is no equivalent fallback
        for messages/share-links/members.
        """
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
        """GET /api/v1/chats/{chat_id}/ — single chat detail (GET_CHAT).

        NOTE: the implementation brief's draft signature pointed at
        `/chats/{id}/manage/`, but aura-chat-service/docs/endpoints.md does
        not list a per-chat `/manage/` detail route — only the plain detail
        endpoint (`GET_CHAT`) and the bulk `/chats/manage/` list
        (`MANAGE_CHATS`). Implemented against the documented contract.
        """
        return self._get(user, f'/api/v1/chats/{chat_id}/')

    def get_chat_messages(self, user, chat_id):
        """GET /api/v1/messages/manage/?chat_id={chat_id} — full history
        without requiring membership (admin view, MANAGE_MESSAGES).

        NOTE: there is no per-chat ``/chats/{id}/messages/manage/`` route in
        aura-chat-service — chat messages are served by the artifact_message
        app mounted at ``/api/v1/messages/`` and the admin endpoint takes the
        chat as a ``chat_id`` query parameter (see MessageManageView)."""
        data = self._get(user, '/api/v1/messages/manage/', params={'chat_id': chat_id})
        if isinstance(data, dict):
            return data.get('results', [])
        return data or []

    def get_chat_members(self, user, chat_id):
        """GET /api/v1/chats/{chat_id}/members/manage/."""
        data = self._get(user, f'/api/v1/chats/{chat_id}/members/manage/')
        if isinstance(data, dict):
            return data.get('results', [])
        return data or []

    # ── Export (manage) ────────────────────────────────────────────────────────

    def _get_binary(self, user, path):
        """GET returning a streaming binary response (PDF/Markdown export).

        Returns the raw ``requests.Response`` (stream=True); the caller must
        iterate and close it. Raises ChatServiceError on any non-OK status."""
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
        """GET /api/v1/chats/{chat_id}/manage/export/{pdf|markdown}/ (MANAGE_CHATS)."""
        suffix = 'pdf' if fmt == 'pdf' else 'markdown'
        return self._get_binary(user, f'/api/v1/chats/{chat_id}/manage/export/{suffix}/')


chat_client = ChatClient()
