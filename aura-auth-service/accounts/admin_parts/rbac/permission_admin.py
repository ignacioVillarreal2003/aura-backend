"""Permission admin configuration."""

from django.contrib import admin
from django.utils.html import format_html
from accounts.models import Permission
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.utils.audit import _is_super_admin_user, _is_admin_or_super_user


@admin.register(Permission)
class PermissionAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for Permission model."""

    list_display = ('name', 'description_short', 'role_count')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ('id',)
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description'),
        }),
    )

    def has_module_permission(self, request):
        return _is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_add_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def description_short(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def role_count(self, obj):
        count = obj.role_links.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    role_count.short_description = 'Asignado a Roles'
