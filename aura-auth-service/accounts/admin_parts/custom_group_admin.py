"""Custom group admin configuration."""

import logging
from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import connections
from django.utils import timezone
from django.utils.html import format_html
from accounts.models import CustomGroup, User
from accounts.admin_parts.common import (
    HelpTextStripMixin,
    _apply_audit_fields,
    _is_super_admin_user,
    log_audit,
    has_permission,
)

logger = logging.getLogger(__name__)


class CustomGroupAdminForm(forms.ModelForm):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(deleted_at__isnull=True).order_by('username'),
        required=False,
        widget=FilteredSelectMultiple('Usuarios', is_stacked=False),
        label='Usuarios',
    )

    class Meta:
        model = CustomGroup
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            try:
                with connections['aura_db'].cursor() as cursor:
                    cursor.execute(
                        'SELECT user_id FROM auth_user_custom_groups WHERE customgroup_id = %s::uuid',
                        [str(self.instance.pk)],
                    )
                    user_ids = [row[0] for row in cursor.fetchall()]
                self.initial['users'] = user_ids
            except Exception:
                logger.exception('Failed to load users for CustomGroupAdminForm')


@admin.register(CustomGroup)
class CustomGroupAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Custom admin for Group model to manage groups."""

    form = CustomGroupAdminForm
    list_display = ('name', 'description_short', 'member_count', 'document_count')
    list_filter = ('created_at',)
    search_fields = ('name',)
    filter_horizontal = ('documents',)
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description', 'documents'),
        }),
        ('Miembros', {
            'fields': ('users',),
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

    def member_count(self, obj):
        # auth_user_custom_groups lives in aura_db; auth_user lives in auth_db.
        # Cross-DB JOIN is impossible, so we count directly from the through table.
        with connections['aura_db'].cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) FROM auth_user_custom_groups WHERE customgroup_id = %s',
                [str(obj.pk)],
            )
            count = cursor.fetchone()[0]
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    member_count.short_description = 'Miembros'

    def document_count(self, obj):
        count = obj.documents.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    document_count.short_description = 'Documentos'

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ('Información Básica', {
                    'fields': ('name', 'description', 'documents'),
                }),
                ('Miembros', {
                    'fields': ('users',),
                }),
            )
        return self.fieldsets

    def has_module_permission(self, request):
        return has_permission(request, 'ADMIN_GROUPS_MANAGE')

    def has_view_permission(self, request, obj=None):
        return has_permission(request, 'ADMIN_GROUPS_MANAGE')

    def has_add_permission(self, request):
        return has_permission(request, 'ADMIN_GROUPS_MANAGE')

    def has_change_permission(self, request, obj=None):
        return has_permission(request, 'ADMIN_GROUPS_MANAGE')

    def has_delete_permission(self, request, obj=None):
        return has_permission(request, 'ADMIN_GROUPS_MANAGE')

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

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if 'users' not in form.cleaned_data:
            return
        group_id = str(form.instance.pk)
        selected_users = list(form.cleaned_data['users'])
        try:
            with connections['aura_db'].cursor() as cursor:
                if selected_users:
                    user_ids = [u.pk for u in selected_users]
                    placeholders = ','.join(['%s'] * len(user_ids))
                    cursor.execute(
                        f'DELETE FROM auth_user_custom_groups '
                        f'WHERE customgroup_id = %s::uuid AND user_id NOT IN ({placeholders})',
                        [group_id] + user_ids,
                    )
                    for uid in user_ids:
                        cursor.execute(
                            'INSERT INTO auth_user_custom_groups (user_id, customgroup_id) '
                            'VALUES (%s, %s::uuid) ON CONFLICT DO NOTHING',
                            [uid, group_id],
                        )
                else:
                    cursor.execute(
                        'DELETE FROM auth_user_custom_groups WHERE customgroup_id = %s::uuid',
                        [group_id],
                    )
        except Exception:
            logger.exception('Failed to sync users for CustomGroup %s', group_id)

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
        action = 'UPDATE' if change else 'CREATE'
        details = {'changed_fields': form.changed_data} if change and form.changed_data else None
        log_audit(
            actor=request.user,
            action=action,
            entity_type='custom_group',
            entity_id=str(obj.pk),
            entity_label=obj.name,
            details=details,
        )

    def delete_model(self, request, obj):
        self._sync_collection_delete(request, obj)
        super().delete_model(request, obj)
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='custom_group',
            entity_id=str(obj.pk),
            entity_label=obj.name,
        )

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self._sync_collection_delete(request, obj)
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='custom_group',
                entity_id=str(obj.pk),
                entity_label=obj.name,
            )
        super().delete_queryset(request, queryset)
