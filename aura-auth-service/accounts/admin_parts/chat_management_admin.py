"""Admin views for Chat management — list, detail, share-link revocation.

Replaces the previous `ChatAdmin(admin.ModelAdmin)` (chat/admin.py) with a
fully custom view pattern, following accounts/admin_parts/mac_admin.py: no
ModelAdmin, no QuerySet-backed ChangeList — plain Django views registered
via the same `admin.site.get_urls` monkeypatch, rendering their own
templates.

Data sources:
  - List view: aura-chat-service `GET /api/v1/chats/manage/` (via
    chat_client.get_chats()), with a deliberate fallback to the local
    aura_db `Chat` ORM mirror if the service call fails — this is the one
    place in this module that tolerates chat-service being down, since
    there's a local mirror to fall back to. A yellow banner makes the
    fallback visible to the admin rather than silently serving stale data.
  - Detail view: the chat's own identity fields (name, creator, timestamps)
    still come from the local `Chat` ORM mirror — same as the previous
    ChatAdmin.change_view did. Messages, share links and members are
    chat-service-API-backed only, with no fallback (there is no local
    mirror for chat_message-level detail beyond what raw SQL already
    reads, and inventing one here would duplicate, not simplify, the
    previous implementation) — each panel independently shows "servicio no
    disponible" on failure instead of breaking the page.

Note on permissions: this section is intentionally **stricter** than
mac_admin.py's `_check_admin_or_superadmin` — the previous
ChatAdmin.has_view_permission required superadmin *or* an elevated admin
session, not plain admin. Chat contents are more sensitive than MAC
configuration, so that restriction is preserved here verbatim as
`_check_chat_access` rather than reusing the looser MAC-style check.
"""

import logging

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db import connections
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect, StreamingHttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse

from accounts.admin_parts.common import _is_super_admin_user, _is_effective_superadmin, has_permission
from accounts.admin_parts.utils.audit import log_audit
from accounts.services.chat_client import ChatServiceError, chat_client
from chat.models import Chat

logger = logging.getLogger(__name__)

_PAGE_SIZE = 20

# Safe whitelist for the ORM-fallback ordering — chat-service validates
# `ordering` itself and silently ignores anything not in its own
# ALLOWED_ORDERINGS, but Django's `.order_by()` raises FieldError on an
# unknown field, which would surface as a 500 if we passed the raw,
# user-controlled `?o=` value straight through in the fallback branch.
_FALLBACK_ORDERING = {
    'created_at': 'created_at',
    '-created_at': '-created_at',
    'name': 'name',
    '-name': '-name',
    'last_message_at': 'last_message_at',
    '-last_message_at': '-last_message_at',
}


# ── Permission check ────────────────────────────────────────────────────────

def _check_chat_access(request):
    if not (has_permission(request, 'ADMIN_CHAT_VIEW') or _is_effective_superadmin(request)):
        raise PermissionDenied


def _ctx(request, **extra):
    return {**admin.site.each_context(request), **extra}


# ── Local-data helpers (auth_user lives in this service's own DB — never
#    fetched from chat-service, which doesn't own it) ───────────────────────

def _resolve_username(user_id):
    if user_id is None:
        return '—'
    with connections['default'].cursor() as cursor:
        cursor.execute('SELECT username FROM auth_user WHERE id = %s', [user_id])
        row = cursor.fetchone()
    return row[0] if row else f'#{user_id}'


def _resolve_usernames_batch(user_ids):
    ids = [uid for uid in user_ids if uid is not None]
    if not ids:
        return {}
    placeholders = ','.join(['%s'] * len(ids))
    with connections['default'].cursor() as cursor:
        cursor.execute(
            f'SELECT id, username FROM auth_user WHERE id IN ({placeholders})',
            ids,
        )
        return {row[0]: row[1] for row in cursor.fetchall()}


def _resolve_user_ids_by_username(search_term):
    """Used only by the ORM fallback path, to replicate the original
    name-OR-creator-username search semantics. The chat-service API path
    only matches chat `name` — confirmed against
    aura-chat-service/apps/chat/repositories/chat_repository.py `list_all`,
    which does `qs.filter(name__icontains=search)` and nothing else;
    chat-service has no way to filter by a username it doesn't own."""
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute(
                'SELECT id FROM auth_user WHERE username ILIKE %s',
                [f'%{search_term}%'],
            )
            return [row[0] for row in cursor.fetchall()]
    except Exception:
        logger.exception('chat_management_admin: auth_db username lookup failed')
        return []


def _format_chat_dt(value):
    """Format a timestamp that may arrive as an ISO string (chat-service
    JSON response) or a native datetime (local ORM row)."""
    if not value:
        return '—'
    try:
        from django.utils import timezone as dj_timezone
        from django.utils.dateparse import parse_datetime

        dt = parse_datetime(value) if isinstance(value, str) else value
        if dt is None:
            return str(value)
        if dj_timezone.is_naive(dt):
            dt = dj_timezone.make_aware(dt, dj_timezone.utc)
        return dj_timezone.localtime(dt).strftime('%d/%m/%Y %H:%M')
    except Exception:
        return str(value)


# ── List view ────────────────────────────────────────────────────────────────

def _chat_list_view(request):
    _check_chat_access(request)

    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    search = request.GET.get('q', '').strip()
    ordering = request.GET.get('o', '-created_at').strip() or '-created_at'

    using_fallback = False
    api_result = chat_client.get_chats(
        request.user,
        page=page,
        page_size=_PAGE_SIZE,
        search=search or None,
        ordering=ordering,
    )

    if api_result is not None:
        chats_raw = api_result.get('results', [])
        total_count = api_result.get('count', len(chats_raw))

        user_ids = [c.get('created_by') for c in chats_raw if c.get('created_by')]
        usernames = _resolve_usernames_batch(user_ids)

        chats = [
            {
                'id': c.get('id'),
                'name': c.get('name'),
                'creator_username': usernames.get(c.get('created_by'), f"#{c.get('created_by')}"),
                'created_at': _format_chat_dt(c.get('created_at')),
                'last_message_at': _format_chat_dt(c.get('last_message_at')),
                'is_locked': bool(c.get('is_locked')),
                'member_count': c.get('member_count', '—'),
            }
            for c in chats_raw
        ]
    else:
        using_fallback = True
        qs = Chat.objects.using('aura_db').filter(deleted_at__isnull=True)
        if search:
            matching_user_ids = _resolve_user_ids_by_username(search)
            qs = qs.filter(Q(name__icontains=search) | Q(created_by__in=matching_user_ids))
        qs = qs.order_by(_FALLBACK_ORDERING.get(ordering, '-created_at'))

        total_count = qs.count()
        start = (page - 1) * _PAGE_SIZE
        page_rows = list(qs[start:start + _PAGE_SIZE])

        user_ids = [c.created_by for c in page_rows if c.created_by]
        usernames = _resolve_usernames_batch(user_ids)

        chats = [
            {
                'id': c.id,
                'name': c.name,
                'creator_username': usernames.get(c.created_by, f"#{c.created_by}"),
                'created_at': _format_chat_dt(c.created_at),
                'last_message_at': _format_chat_dt(c.last_message_at),
                # Not available from the local mirror — chat-service owns
                # is_locked/member_count and isn't reachable right now.
                'is_locked': False,
                'member_count': '—',
            }
            for c in page_rows
        ]

    total_pages = max(1, (total_count + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = min(page, total_pages)

    ctx = _ctx(
        request,
        title='Todos los chats',
        chats=chats,
        search=search,
        ordering=ordering,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        has_prev=page > 1,
        has_next=page < total_pages,
        using_fallback=using_fallback,
        opts=Chat._meta,
    )
    return TemplateResponse(request, 'admin/chat_management/list.html', ctx)


# ── Detail view ──────────────────────────────────────────────────────────────

def _load_chat_messages(request, chat_id):
    try:
        raw = chat_client.get_chat_messages(request.user, chat_id)
    except ChatServiceError as exc:
        logger.warning('chat_management_admin: failed to load messages for chat %s: %s', chat_id, exc)
        return [], 'Servicio de chat no disponible — no se pudo cargar el historial.'
    except Exception:
        logger.exception('chat_management_admin: unexpected error loading messages for chat %s', chat_id)
        return [], 'Error al cargar mensajes.'

    user_ids = list({
        m.get('created_by') for m in raw
        if m.get('sender_type') == 'user' and m.get('created_by')
    })
    usernames = _resolve_usernames_batch(user_ids)

    rows = []
    for m in raw:
        sender_type = m.get('sender_type')
        created_by = m.get('created_by')
        rows.append({
            'is_user': sender_type == 'user',
            'label': usernames.get(created_by, f'#{created_by}') if sender_type == 'user' else 'sistema',
            'timestamp': _format_chat_dt(m.get('created_at')),
            'message': m.get('message') or '',
        })
    return rows, None


def _load_chat_share_links(request, chat_id):
    try:
        links = chat_client.get_chat_share_links(request.user, chat_id)
    except ChatServiceError as exc:
        logger.warning('chat_management_admin: failed to load share links for chat %s: %s', chat_id, exc)
        return [], 'Servicio no disponible.'
    except Exception:
        logger.exception('chat_management_admin: unexpected error loading share links for chat %s', chat_id)
        return [], 'Servicio no disponible.'

    rows = []
    for link in links:
        if not link.get('is_active', True):
            continue
        rows.append({
            'token': link.get('token', ''),
            'expires_label': _format_chat_dt(link.get('expires_at')) if link.get('expires_at') else 'Sin vencimiento',
            'revoke_url': reverse('admin:chat_management_revoke_link', args=[chat_id, link.get('id')]),
        })
    return rows, None


def _load_chat_members(request, chat_id):
    try:
        members = chat_client.get_chat_members(request.user, chat_id)
    except ChatServiceError as exc:
        logger.warning('chat_management_admin: failed to load members for chat %s: %s', chat_id, exc)
        return [], 'Servicio no disponible.'
    except Exception:
        logger.exception('chat_management_admin: unexpected error loading members for chat %s', chat_id)
        return [], 'Servicio no disponible.'

    member_ids = [m.get('member_id') for m in members if m.get('member_id')]
    usernames = _resolve_usernames_batch(member_ids)
    rows = [
        {
            'username': usernames.get(m.get('member_id'), f"#{m.get('member_id')}"),
            'role': m.get('role') or '—',
            'status': m.get('status') or '—',
        }
        for m in members
    ]
    return rows, None


def _chat_detail_view(request, chat_id):
    _check_chat_access(request)

    try:
        chat_obj = Chat.objects.using('aura_db').get(pk=chat_id, deleted_at__isnull=True)
    except Chat.DoesNotExist:
        raise Http404('Chat no encontrado.')

    message_rows, messages_error = _load_chat_messages(request, chat_id)
    share_links, share_links_error = _load_chat_share_links(request, chat_id)
    member_rows, members_error = _load_chat_members(request, chat_id)

    ctx = _ctx(
        request,
        title=f'Chat — {chat_obj.name}',
        chat=chat_obj,
        creator_username=_resolve_username(chat_obj.created_by),
        created_at=_format_chat_dt(chat_obj.created_at),
        last_message_at=_format_chat_dt(chat_obj.last_message_at),
        message_rows=message_rows,
        messages_error=messages_error,
        share_links=share_links,
        share_links_error=share_links_error,
        member_rows=member_rows,
        members_error=members_error,
        back_url=reverse('admin:chat_management_list'),
        opts=Chat._meta,
    )
    return TemplateResponse(request, 'admin/chat_management/detail.html', ctx)


# ── Revoke share link (destructive -> POST only, audited) ──────────────────

def _chat_revoke_share_link_view(request, chat_id, link_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    _check_chat_access(request)

    try:
        chat_client.delete_share_link(request.user, chat_id, link_id)
    except ChatServiceError as exc:
        messages.error(request, f'No se pudo revocar el enlace: {exc}')
    else:
        messages.success(request, 'Enlace de compartición revocado correctamente.')
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='chat_share_link',
            entity_id=str(link_id),
            entity_label=f'{request.user.username} revocó un enlace de compartición del chat #{chat_id}',
            details={'chat_id': chat_id, 'link_id': link_id},
            source='admin',
            request=request,
        )

    return HttpResponseRedirect(reverse('admin:chat_management_detail', args=[chat_id]))


# ── Export (manage) — streams the chat-service admin export ────────────────────

def _chat_export_view(request, chat_id, fmt):
    _check_chat_access(request)
    if fmt not in ('pdf', 'markdown'):
        raise Http404('Formato de exportación no soportado.')

    try:
        upstream = chat_client.export_chat(request.user, chat_id, fmt)
    except ChatServiceError as exc:
        messages.error(request, f'No se pudo exportar el chat: {exc}')
        return HttpResponseRedirect(reverse('admin:chat_management_detail', args=[chat_id]))

    response = StreamingHttpResponse(
        upstream.iter_content(chunk_size=8192),
        content_type=upstream.headers.get(
            'Content-Type',
            'application/pdf' if fmt == 'pdf' else 'text/markdown',
        ),
    )
    disposition = upstream.headers.get('Content-Disposition')
    if not disposition:
        ext = 'pdf' if fmt == 'pdf' else 'md'
        disposition = f'attachment; filename="chat_{chat_id}.{ext}"'
    response['Content-Disposition'] = disposition
    return response


# ── URL registration (same admin.site.get_urls monkeypatch as mac_admin.py) ─

_prev_get_urls = admin.site.get_urls


def _chat_management_get_urls(self):
    urls = _prev_get_urls()
    custom_urls = [
        path('chats/', self.admin_view(_chat_list_view), name='chat_management_list'),
        path('chats/<int:chat_id>/', self.admin_view(_chat_detail_view), name='chat_management_detail'),
        path(
            'chats/<int:chat_id>/revoke/<str:link_id>/',
            self.admin_view(_chat_revoke_share_link_view),
            name='chat_management_revoke_link',
        ),
        path(
            'chats/<int:chat_id>/export/<str:fmt>/',
            self.admin_view(_chat_export_view),
            name='chat_management_export',
        ),
    ]
    return custom_urls + urls


admin.site.get_urls = _chat_management_get_urls.__get__(admin.site, admin.AdminSite)
