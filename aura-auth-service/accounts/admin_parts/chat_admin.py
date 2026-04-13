"""Admin view for Gestión de Chats — reads chat table from aura_db."""

import logging

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import connections, OperationalError
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from accounts.admin_parts.common import _is_admin_or_super_user

logger = logging.getLogger(__name__)

_PAGE_SIZE = 50


def _chat_list_view(request):
    if not _is_admin_or_super_user(request.user):
        raise PermissionDenied

    try:
        page = max(1, int(request.GET.get('p', 1)))
    except (TypeError, ValueError):
        page = 1

    search = request.GET.get('q', '').strip()
    offset = (page - 1) * _PAGE_SIZE

    chats = []
    total = 0
    error = None

    try:
        with connections['aura_db'].cursor() as cursor:
            base_where = "WHERE deleted_at IS NULL"
            params: list = []

            if search:
                base_where += " AND (name ILIKE %s OR CAST(id AS TEXT) LIKE %s)"
                pattern = f"%{search}%"
                params.extend([pattern, pattern])

            cursor.execute(
                f"SELECT COUNT(*) FROM chat {base_where}",
                params,
            )
            total = cursor.fetchone()[0]

            cursor.execute(
                f"""
                SELECT id, name, created_by, created_at, last_message_at
                FROM chat
                {base_where}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [_PAGE_SIZE, offset],
            )
            rows = cursor.fetchall()
            chats = [
                {
                    'id': row[0],
                    'name': row[1],
                    'created_by': row[2],
                    'created_at': row[3],
                    'last_message_at': row[4],
                }
                for row in rows
            ]
    except OperationalError as exc:
        error = 'No se pudo conectar a aura_db. Verifique la configuración de base de datos.'
        logger.warning('chat_list_view: aura_db connection failed: %s', exc)

    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page_range = range(max(1, page - 2), min(total_pages, page + 2) + 1)

    context = {
        **admin.site.each_context(request),
        'title': 'Gestión de Chats',
        'subtitle': 'Todos los chats del sistema',
        'chats': chats,
        'total': total,
        'page': page,
        'total_pages': total_pages,
        'page_range': page_range,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'search': search,
        'error': error,
        'generated_at': timezone.now(),
    }
    return TemplateResponse(request, 'admin/chats/index.html', context)


# Follow the same instance-method patch pattern as dashboard_admin.py.
# dashboard_admin already replaced get_urls on the instance; we save that
# version and prepend our own URL so both coexist without recursion.
_prev_get_urls = admin.site.get_urls


def _custom_get_urls(self):
    urls = _prev_get_urls()
    custom_urls = [
        path('chats/', self.admin_view(_chat_list_view), name='chat_list'),
    ]
    return custom_urls + urls


admin.site.get_urls = _custom_get_urls.__get__(admin.site, admin.AdminSite)
