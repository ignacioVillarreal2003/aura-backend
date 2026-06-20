"""Permission-in-role admin configuration."""

from django.contrib import admin
from accounts.models import PermissionInRole
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.utils.audit import _is_super_admin_user, _is_admin_or_super_user, _is_effective_superadmin
from accounts.admin_parts.utils.permissions import has_permission


@admin.register(PermissionInRole)
class PermissionInRoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for PermissionInRole relationship."""

    list_display = ('role', 'permission')
    list_filter = ('role',)
    search_fields = ('role__name', 'permission__name')
    readonly_fields = ('id',)

    fieldsets = (
        ('Asignación', {
            'fields': ('id', 'role', 'permission'),
        }),
    )

    def has_module_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        return has_permission(request, 'ADMIN_ROLES_VIEW')

    def has_add_permission(self, request):
        return has_permission(request, 'ADMIN_ROLES_EDIT') or _is_effective_superadmin(request)

    def has_change_permission(self, request, obj=None):
        return has_permission(request, 'ADMIN_ROLES_EDIT') or _is_effective_superadmin(request)

    def has_delete_permission(self, request, obj=None):
        return has_permission(request, 'ADMIN_ROLES_EDIT') or _is_effective_superadmin(request)
