"""FAU role admin configuration."""

from django.contrib import admin
from django.utils.html import format_html
from accounts.models import FauRole, PermissionInFauRole
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.utils.audit import _is_admin_or_super_user, _is_super_admin_user


class PermissionInFauRoleInline(admin.TabularInline):
    """Inline for assigning permissions to a FAU role."""

    model = PermissionInFauRole
    extra = 1
    can_delete = False
    fields = ('permission',)
    verbose_name = 'Permiso'
    verbose_name_plural = 'Permisos asignados'

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_add_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FauRole)
class FauRoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for FauRole model."""

    list_display = ('name', 'power_badge', 'description')
    search_fields = ('name', 'description')
    readonly_fields = ()
    ordering = ('-power',)
    actions = None
    actions_selection_counter = False
    inlines = [PermissionInFauRoleInline]

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description'),
        }),
        ('Jerarquía', {
            'fields': ('power',),
            'description': (
                'El nivel de poder define la jerarquía entre roles FAU. '
                'Mayor número = mayor poder. Debe ser único.'
            ),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('name',)
        return self.readonly_fields

    def power_badge(self, obj):
        if obj.power is not None:
            return format_html(
                '<span style="background-color: #417690; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">{}</span>',
                obj.power,
            )
        return format_html('<span style="color: #999;">-</span>')
    power_badge.short_description = 'Nivel Jerárquico'
    power_badge.admin_order_field = 'power'

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
