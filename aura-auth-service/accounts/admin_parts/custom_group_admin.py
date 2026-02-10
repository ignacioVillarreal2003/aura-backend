"""Custom group admin configuration."""

from django.contrib import admin
from django.utils.html import format_html
from accounts.models import CustomGroup
from accounts.admin_parts.common import HelpTextStripMixin, _apply_audit_fields, _is_super_admin_user


@admin.register(CustomGroup)
class CustomGroupAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Custom admin for Group model to manage groups."""

    list_display = ('name', 'description_short', 'document_count', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('documents',)

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
        return _is_super_admin_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_add_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def save_model(self, request, obj, form, change):
        _apply_audit_fields(obj, request.user, is_create=not change)
        super().save_model(request, obj, form, change)
