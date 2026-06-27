"""Vistas del admin para gestionar chats: listado, detalle y exportacion.

El listado usa el chat-service y, si no responde, cae al espejo local en
aura_db (mostrando un aviso). El detalle saca los datos del chat de la base
local y los mensajes/miembros del chat-service. El acceso es solo para
superadmin o admin con permiso, porque el contenido de los chats es sensible.
"""

import logging

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db import connections
from django.http import Http404, HttpResponseRedirect, StreamingHttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse

from apps.accounts.admin_parts.common import _is_super_admin_user, _is_effective_superadmin, has_permission
from apps.accounts.services.chat_client import ChatServiceError, chat_client
from apps.chat.models import Chat

logger = logging.getLogger(__name__)

_PAGE_SIZE = 20

_FALLBACK_ORDERING = {
    'created_at': 'created_at',
    '-created_at': '-created_at',
    'name': 'name',
    '-name': '-name',
    'last_message_at': 'last_message_at',
    '-last_message_at': '-last_message_at',
}



def _check_chat_access(request):
    if not (has_permission(request, 'ADMIN_CHAT_VIEW') or _is_effective_superadmin(request)):
        raise PermissionDenied


def _ctx(request, **extra):
    return {**admin.site.each_context(request), **extra}



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
    """Busca ids de usuario por username, solo para el fallback ORM."""
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
    """Formatea una fecha que puede venir como texto ISO o como datetime."""
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


_DOC_STATUS_LABELS = {
    'processed': 'Procesado',
    'uploaded': 'Cargado',
    'failed': 'Fallido',
}


def _format_size(num_bytes):
    if not num_bytes:
        return '—'
    size = float(num_bytes)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024.0:
            return f'{size:.1f} {unit}'
        size /= 1024.0
    return f'{size:.1f} PB'


def _load_chat_documents(chat_id):
    """Documentos subidos a este chat, leidos directo de aura_db."""
    try:
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, mime_type, file_size_bytes, status, created_by, created_at
                FROM document
                WHERE chat_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC
                """,
                [chat_id],
            )
            rows = cursor.fetchall()
    except Exception:
        logger.exception('chat_management_admin: failed to load documents for chat %s', chat_id)
        return [], 'No se pudieron cargar los documentos.'

    creator_ids = [r[5] for r in rows if r[5]]
    usernames = _resolve_usernames_batch(creator_ids)

    docs = [
        {
            'id': r[0],
            'name': r[1],
            'mime_type': r[2] or '—',
            'size': _format_size(r[3]),
            'status': _DOC_STATUS_LABELS.get((r[4] or '').lower(), r[4] or '—'),
            'uploaded_by': usernames.get(r[5], f'#{r[5]}') if r[5] else '—',
            'created_at': _format_chat_dt(r[6]),
        }
        for r in rows
    ]
    return docs, None


def _chat_detail_view(request, chat_id):
    _check_chat_access(request)

    try:
        chat_obj = Chat.objects.using('aura_db').get(pk=chat_id, deleted_at__isnull=True)
    except Chat.DoesNotExist:
        raise Http404('Chat no encontrado.')

    message_rows, messages_error = _load_chat_messages(request, chat_id)
    member_rows, members_error = _load_chat_members(request, chat_id)
    document_rows, documents_error = _load_chat_documents(chat_id)

    ctx = _ctx(
        request,
        title=f'Chat - {chat_obj.name}',
        chat=chat_obj,
        creator_username=_resolve_username(chat_obj.created_by),
        created_at=_format_chat_dt(chat_obj.created_at),
        last_message_at=_format_chat_dt(chat_obj.last_message_at),
        message_rows=message_rows,
        messages_error=messages_error,
        member_rows=member_rows,
        members_error=members_error,
        document_rows=document_rows,
        documents_error=documents_error,
        back_url=reverse('admin:chat_management_list'),
        opts=Chat._meta,
    )
    return TemplateResponse(request, 'admin/chat_management/detail.html', ctx)



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



_prev_get_urls = admin.site.get_urls


def _chat_management_get_urls(self):
    urls = _prev_get_urls()
    custom_urls = [
        path('chats/', self.admin_view(_chat_list_view), name='chat_management_list'),
        path('chats/<int:chat_id>/', self.admin_view(_chat_detail_view), name='chat_management_detail'),
        path(
            'chats/<int:chat_id>/export/<str:fmt>/',
            self.admin_view(_chat_export_view),
            name='chat_management_export',
        ),
    ]
    return custom_urls + urls


admin.site.get_urls = _chat_management_get_urls.__get__(admin.site, admin.AdminSite)
