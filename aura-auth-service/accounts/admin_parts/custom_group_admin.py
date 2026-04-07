"""Custom group admin configuration."""

import logging
from django.contrib import admin
from django.db import connections
from django.utils import timezone
from django.utils.html import format_html
from accounts.models import CustomGroup
from accounts.admin_parts.common import (
    HelpTextStripMixin,
    _apply_audit_fields,
    _is_super_admin_user,
    _is_admin_or_super_user,
)

logger = logging.getLogger(__name__)


@admin.register(CustomGroup)
class CustomGroupAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Custom admin for Group model to manage groups."""

    list_display = ('name', 'description_short', 'document_count')
    list_filter = ('created_at',)
    search_fields = ('name',)
    filter_horizontal = ('documents',)
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description', 'documents'),
        }),
        ('Información de Auditoría', {
            'fields': (
                'created_at',
                'created_by',
                'updated_at',
                'updated_by',
                'deleted_at',
                'deleted_by',
            ),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
    )

    def description_short(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def document_count(self, obj):
        count = obj.documents.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    document_count.short_description = 'Documentos'

    def has_module_permission(self, request):
        return _is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_add_permission(self, request):
        return _is_admin_or_super_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def _sync_collection_create_or_update(self, request, obj, old_name=None, is_create=False):
        try:
            with connections['aura_db'].cursor() as cursor:
                if old_name and old_name != obj.name:
                    cursor.execute(
                        """
                        UPDATE document_collection
                        SET name = %s,
                            updated_by = %s,
                            updated_at = %s
                        WHERE name = %s AND deleted_at IS NULL
                        """,
                        [obj.name, request.user.id, timezone.now(), old_name],
                    )
                    if cursor.rowcount == 0:
                        cursor.execute(
                            """
                            INSERT INTO document_collection (name, created_by, created_at)
                            VALUES (%s, %s, %s)
                            """,
                            [obj.name, request.user.id, timezone.now()],
                        )
                    return

                cursor.execute(
                    """
                    SELECT id FROM document_collection
                    WHERE name = %s AND deleted_at IS NULL
                    """,
                    [obj.name],
                )
                exists = cursor.fetchone() is not None
                if is_create and not exists:
                    cursor.execute(
                        """
                        INSERT INTO document_collection (name, created_by, created_at)
                        VALUES (%s, %s, %s)
                        """,
                        [obj.name, request.user.id, timezone.now()],
                    )
                elif exists:
                    cursor.execute(
                        """
                        UPDATE document_collection
                        SET updated_by = %s,
                            updated_at = %s
                        WHERE name = %s AND deleted_at IS NULL
                        """,
                        [request.user.id, timezone.now(), obj.name],
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO document_collection (name, created_by, created_at)
                        VALUES (%s, %s, %s)
                        """,
                        [obj.name, request.user.id, timezone.now()],
                    )
        except Exception:
            logger.exception('Failed to sync CustomGroup to aura_db.document_collection')

    def _sync_collection_delete(self, request, obj):
        try:
            with connections['aura_db'].cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE document_collection
                    SET deleted_by = %s,
                        deleted_at = %s
                    WHERE name = %s AND deleted_at IS NULL
                    """,
                    [request.user.id, timezone.now(), obj.name],
                )
        except Exception:
            logger.exception('Failed to soft-delete document_collection in aura_db')

    def save_model(self, request, obj, form, change):
        old_name = None
        if obj.pk:
            old_name = CustomGroup.objects.filter(pk=obj.pk).values_list('name', flat=True).first()
        _apply_audit_fields(obj, request.user, is_create=not change)
        super().save_model(request, obj, form, change)
        self._sync_collection_create_or_update(
            request,
            obj,
            old_name=old_name,
            is_create=not change,
        )

    def delete_model(self, request, obj):
        self._sync_collection_delete(request, obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._sync_collection_delete(request, obj)
        super().delete_queryset(request, queryset)
