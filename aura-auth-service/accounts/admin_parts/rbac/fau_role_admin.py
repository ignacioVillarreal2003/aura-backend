"""FAU role admin configuration."""

from django.contrib import admin
from accounts.models import FauRole
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.utils.audit import _is_admin_or_super_user, _is_super_admin_user


@admin.register(FauRole)
class FauRoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for FauRole model."""

    list_display = ('name', 'description')
    search_fields = ('name', 'description')
    readonly_fields = ('id',)

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
