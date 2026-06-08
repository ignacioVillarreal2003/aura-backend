"""
Chat admin — read-only view of all chats in aura_db.

All chat data lives in aura_db.  User data lives in auth_db.
Cross-DB lookups are handled exclusively via raw SQL — no ORM joins across DBs.
"""

import logging

from django.contrib import admin
from django.db import connections
from django.db.models import Q
from django.utils.html import escape, format_html, mark_safe

from accounts.admin_parts.common import _is_admin_or_super_user, _is_super_admin_user
from chat.models import Chat

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_username(user_id):
    """Return the username for a given auth_user.id, or '#<id>' if not found."""
    if user_id is None:
        return '—'
    with connections['default'].cursor() as cursor:
        cursor.execute(
            'SELECT username FROM auth_user WHERE id = %s',
            [user_id],
        )
        row = cursor.fetchone()
    return row[0] if row else f'#{user_id}'


def _resolve_usernames_batch(user_ids):
    """Return {user_id: username} for a collection of IDs. Single query to auth_db."""
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


def _last_message_preview(chat_id):
    """Fetch the most-recent non-deleted message for a chat from aura_db."""
    with connections['aura_db'].cursor() as cursor:
        cursor.execute(
            """
            SELECT message FROM chat_message
            WHERE chat_id = %s AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [chat_id],
        )
        row = cursor.fetchone()
    if not row:
        return '—'
    text = row[0] or ''
    return (text[:80] + '…') if len(text) > 80 else text


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    """Read-only admin for the Chat model (data in aura_db)."""

    # ------------------------------------------------------------------
    # List view
    # ------------------------------------------------------------------
    list_display = (
        'id',
        'chat_name',
        'creator_username',
        'created_at_fmt',
        'last_message_at_fmt',
        'last_message_preview',
        'status_badge',
    )
    list_display_links = ('id', 'chat_name')
    search_fields = ('name',)   # needed to render the search bar; logic is in get_search_results
    ordering = ('-created_at',)
    actions = None
    actions_selection_counter = False

    # ------------------------------------------------------------------
    # Detail (change) view — all fields read-only
    # ------------------------------------------------------------------
    readonly_fields = (
        'chat_id_display',
        'chat_name_display',
        'creator_display',
        'created_at_detail',
        'last_message_at_detail',
        'message_history',
    )
    fieldsets = (
        ('Información del Chat', {
            'fields': (
                'chat_id_display',
                'chat_name_display',
                'creator_display',
                'created_at_detail',
                'last_message_at_detail',
            ),
        }),
        ('Historial de Mensajes', {
            'fields': ('message_history',),
        }),
    )

    # ------------------------------------------------------------------
    # Permissions — fully read-only
    # ------------------------------------------------------------------
    def has_module_permission(self, request):
        return _is_super_admin_user(request.user) or getattr(request, 'is_elevated', False)

    def has_view_permission(self, request, obj=None):
        return _is_super_admin_user(request.user) or getattr(request, 'is_elevated', False)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # has_view_permission=True keeps detail links clickable

    def has_delete_permission(self, request, obj=None):
        return False

    # ------------------------------------------------------------------
    # Queryset — aura_db, hide soft-deleted
    # ------------------------------------------------------------------
    def get_queryset(self, request):
        qs = (
            Chat.objects.using('aura_db')
            .filter(deleted_at__isnull=True)
            .order_by('-created_at')
        )
        return qs

    # ------------------------------------------------------------------
    # Search — cross-DB: resolves creator usernames from auth_db
    # ------------------------------------------------------------------
    def get_search_results(self, request, queryset, search_term):
        if not search_term:
            return queryset, False

        # Resolve matching user IDs from auth_db (no ORM cross-DB join).
        matching_user_ids = []
        try:
            with connections['default'].cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM auth_user WHERE username ILIKE %s",
                    [f'%{search_term}%'],
                )
                matching_user_ids = [row[0] for row in cursor.fetchall()]
        except Exception:
            logger.exception('ChatAdmin: auth_db username lookup failed')

        qs = queryset.filter(
            Q(name__icontains=search_term)
            | Q(created_by__in=matching_user_ids)
        )
        return qs, False

    # ------------------------------------------------------------------
    # List-view column methods
    # ------------------------------------------------------------------
    def chat_name(self, obj):
        return obj.name
    chat_name.short_description = 'Nombre'
    chat_name.admin_order_field = 'name'

    def creator_username(self, obj):
        return _resolve_username(obj.created_by)
    creator_username.short_description = 'Creado por'

    def created_at_fmt(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y %H:%M')
        return '—'
    created_at_fmt.short_description = 'Creado el'
    created_at_fmt.admin_order_field = 'created_at'

    def last_message_at_fmt(self, obj):
        if obj.last_message_at:
            return obj.last_message_at.strftime('%d/%m/%Y %H:%M')
        return '—'
    last_message_at_fmt.short_description = 'Último mensaje'
    last_message_at_fmt.admin_order_field = 'last_message_at'

    def last_message_preview(self, obj):
        return _last_message_preview(obj.pk)
    last_message_preview.short_description = 'Vista previa'

    def status_badge(self, obj):
        if obj.deleted_at:
            return format_html(
                '<span style="background:#fee2e2;color:#991b1b;border-radius:999px;'
                'padding:2px 9px;font-size:11px;font-weight:700;">Eliminado</span>'
            )
        return format_html(
            '<span style="background:#d1fae5;color:#065f46;border-radius:999px;'
            'padding:2px 9px;font-size:11px;font-weight:700;">Activo</span>'
        )
    status_badge.short_description = 'Estado'

    # ------------------------------------------------------------------
    # Detail-view readonly field renderers
    # ------------------------------------------------------------------
    def chat_id_display(self, obj):
        return obj.pk
    chat_id_display.short_description = 'ID'

    def chat_name_display(self, obj):
        return obj.name
    chat_name_display.short_description = 'Nombre'

    def creator_display(self, obj):
        return _resolve_username(obj.created_by)
    creator_display.short_description = 'Creado por'

    def created_at_detail(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y %H:%M')
        return '—'
    created_at_detail.short_description = 'Creado el'

    def last_message_at_detail(self, obj):
        if obj.last_message_at:
            return obj.last_message_at.strftime('%d/%m/%Y %H:%M')
        return '—'
    last_message_at_detail.short_description = 'Último mensaje'

    def message_history(self, obj):
        """Render a styled, scrollable bubble-log of all non-deleted messages."""
        try:
            with connections['aura_db'].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, message, sender_type, created_by, created_at
                    FROM chat_message
                    WHERE chat_id = %s AND deleted_at IS NULL
                    ORDER BY created_at ASC
                    """,
                    [obj.pk],
                )
                rows = cursor.fetchall()
        except Exception:
            logger.exception('ChatAdmin: failed to load messages for chat %s', obj.pk)
            return format_html('<p style="color:#991b1b;">Error al cargar mensajes.</p>')

        if not rows:
            return format_html(
                '<p style="color:#697688;font-size:13px;">Sin mensajes.</p>'
            )

        # Batch-resolve usernames for user-type messages.
        user_ids = list({row[3] for row in rows if row[2] == 'user' and row[3]})
        usernames = _resolve_usernames_batch(user_ids)

        # Build HTML — all user content is escaped before insertion.
        parts = []
        for _msg_id, message, sender_type, created_by, created_at in rows:
            ts = created_at.strftime('%d/%m/%Y %H:%M') if created_at else ''

            if sender_type == 'user':
                label = usernames.get(created_by, f'#{created_by}')
                bubble_bg = '#dbeafe'       # light blue
                label_color = '#1e40af'
            else:
                label = 'sistema'
                bubble_bg = '#f3f4f6'       # light grey
                label_color = '#374151'

            parts.append(
                f'<div style="margin-bottom:10px;">'
                f'<div style="background:{bubble_bg};border-radius:8px;'
                f'padding:9px 13px;max-width:85%;display:inline-block;'
                f'font-size:13px;font-family:sans-serif;line-height:1.5;">'
                f'<div style="margin-bottom:3px;">'
                f'<span style="font-weight:700;color:{label_color};">'
                f'{escape(label)}</span>'
                f'<span style="color:#9ca3af;font-size:11px;margin-left:8px;">'
                f'{escape(ts)}</span>'
                f'</div>'
                f'<div style="color:#1f2937;white-space:pre-wrap;word-break:break-word;">'
                f'{escape(message)}'
                f'</div>'
                f'</div>'
                f'</div>'
            )

        container = (
            '<div style="max-height:600px;overflow-y:auto;padding:14px;'
            'background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;">'
            + ''.join(parts)
            + '</div>'
        )
        return mark_safe(container)

    message_history.short_description = 'Mensajes'

    # ------------------------------------------------------------------
    # Detail view — suppress all editing UI
    # ------------------------------------------------------------------
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra = extra_context or {}
        extra.update({
            'show_save': False,
            'show_save_and_continue': False,
            'show_save_and_add_another': False,
            'show_delete': False,
        })
        return super().change_view(request, object_id, form_url, extra_context=extra)
