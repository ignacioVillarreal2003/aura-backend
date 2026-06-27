"""Vista de auditoria: lee la tabla audit_log de auth_db."""

import html as _html
import logging

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.urls import path

from apps.accounts.admin_parts.common import _is_super_admin_user, _is_admin_or_super_user, _is_effective_superadmin
from apps.accounts.admin_parts.utils.permissions import has_permission
from apps.accounts.models import AuditLog

logger = logging.getLogger(__name__)

_PAGE_SIZE = 50

_ACTION_LABELS = {
    'CREATE': ('Crear', '#16a34a'),
    'UPDATE': ('Actualizar', '#2563eb'),
    'DELETE': ('Eliminar', '#dc2626'),
    'LOGIN': ('Login', '#7c3aed'),
    'LOGIN_FAILED': ('Login fallido', '#f97316'),
    'LOGOUT': ('Logout', '#6b7280'),
    'ELEVATION_START': ('Elevación iniciada', '#b45309'),
    'ELEVATION_END': ('Elevación finalizada', '#6b7280'),
    'ELEVATION_FAILED': ('Elevación fallida', '#dc2626'),
}

_SOURCE_LABELS = {
    'admin': 'Admin',
    'superadmin': 'SUPERADMIN',
    'api': 'API',
}

_ENTITY_LABELS = {
    'auth_user': 'Usuario',
    'custom_group': 'Grupo',
    'role': 'Rol sistema',
    'permission': 'Permiso',
    'user_role': 'Asignación rol',
}


def _audit_list_view(request):
    if not has_permission(request, 'ADMIN_AUDIT_VIEW'):
        raise PermissionDenied

    try:
        page = max(1, int(request.GET.get('p', 1)))
    except (TypeError, ValueError):
        page = 1

    search = request.GET.get('q', '').strip()
    filter_action = request.GET.get('action', '').strip()
    filter_entity = request.GET.get('entity', '').strip()

    qs = AuditLog.objects.all()

    if not (has_permission(request, 'ADMIN_AUDIT_VIEW_ALL') or _is_effective_superadmin(request)):
        qs = qs.filter(source='admin')

    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(actor_username__icontains=search)
            | Q(entity_label__icontains=search)
            | Q(entity_id__icontains=search)
        )

    if filter_action:
        qs = qs.filter(action=filter_action)

    if filter_entity:
        qs = qs.filter(entity_type=filter_entity)

    total = qs.count()
    offset = (page - 1) * _PAGE_SIZE
    entries = list(qs[offset: offset + _PAGE_SIZE].values(
        'id', 'timestamp', 'actor_id', 'actor_username',
        'action', 'entity_type', 'entity_id', 'entity_label',
        'details', 'source',
    ))

    for entry in entries:
        action_key = entry['action']
        label, color = _ACTION_LABELS.get(action_key, (action_key, '#374151'))
        entry['action_label'] = label
        entry['action_color'] = color
        entry['entity_type_label'] = _ENTITY_LABELS.get(entry['entity_type'], entry['entity_type'])
        entry['source_label'] = _SOURCE_LABELS.get(entry['source'], entry['source'].upper() if entry['source'] else '—')

        raw_label = entry.get('entity_label') or ''
        words = raw_label.split(' ')
        if len(words) >= 2:
            escaped = [_html.escape(w) for w in words]
            escaped[0] = f'<strong>{escaped[0]}</strong>'
            escaped[-1] = f'<strong>{escaped[-1]}</strong>'
            entry['entity_label_html'] = ' '.join(escaped)
        elif words and words[0]:
            entry['entity_label_html'] = f'<strong>{_html.escape(raw_label)}</strong>'
        else:
            entry['entity_label_html'] = '—'

    available_actions = list(
        qs.values_list('action', flat=True).distinct().order_by('action')
    )
    available_entities = list(
        qs.values_list('entity_type', flat=True).distinct().order_by('entity_type')
    )

    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page_range = range(max(1, page - 2), min(total_pages, page + 2) + 1)

    context = {
        **admin.site.each_context(request),
        'title': 'Registro de acciones',
        'entries': entries,
        'total': total,
        'page': page,
        'total_pages': total_pages,
        'page_range': page_range,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'search': search,
        'filter_action': filter_action,
        'filter_entity': filter_entity,
        'available_actions': available_actions,
        'available_entities': available_entities,
        'action_labels': _ACTION_LABELS,
        'entity_labels': _ENTITY_LABELS,
    }
    return TemplateResponse(request, 'admin/auditoria/index.html', context)


_prev_get_urls = admin.site.get_urls


def _audit_get_urls(self):
    urls = _prev_get_urls()
    custom_urls = [
        path('auditoria/', self.admin_view(_audit_list_view), name='auditoria_list'),
    ]
    return custom_urls + urls


admin.site.get_urls = _audit_get_urls.__get__(admin.site, admin.AdminSite)
