"""Role/permission admin configuration."""

from django.contrib import admin
from django.utils.html import format_html
from accounts.models import User, Role, Permission, UserRole, PermissionInRole
from accounts.admin_parts.common import (
    HelpTextStripMixin,
    HelpTextStripInlineMixin,
    _is_super_admin_user,
)


@admin.register(Role)
class RoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for Role model."""

    list_display = ('name', 'description_short', 'permission_count')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ('id',)

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description'),
        }),
    )

    inlines = []

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

    def description_short(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def permission_count(self, obj):
        count = obj.permission_links.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    permission_count.short_description = 'Permisos'


@admin.register(Permission)
class PermissionAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for Permission model."""

    list_display = ('name', 'description_short', 'role_count')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ('id',)

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description'),
        }),
    )

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


class PermissionInRoleInline(HelpTextStripInlineMixin, admin.TabularInline):
    """Inline admin for assigning permissions to roles."""
    model = PermissionInRole
    extra = 1
    fields = ('permission',)
    verbose_name = 'Permiso'
    verbose_name_plural = 'Permisos'


RoleAdmin.inlines = [PermissionInRoleInline]


class UserRoleInline(HelpTextStripInlineMixin, admin.TabularInline):
    """Inline admin for assigning roles to users."""
    model = UserRole
    extra = 1
    fields = ('role', 'created_at', 'created_by', 'deleted_at', 'deleted_by')
    readonly_fields = ('created_at', 'created_by', 'deleted_at', 'deleted_by')
    verbose_name = 'Rol'
    verbose_name_plural = 'Roles'


@admin.register(UserRole)
class UserRoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for UserRole relationship."""

    list_display = ('user', 'role', 'created_at', 'created_by', 'deleted_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'role__name')
    readonly_fields = ('id', 'created_at', 'created_by', 'deleted_at', 'deleted_by')

    fieldsets = (
        ('Asignación', {
            'fields': ('id', 'user', 'role'),
        }),
        ('Metadatos', {
            'fields': ('created_at', 'created_by', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',),
        }),
    )

    def get_list_display(self, request):
        if _is_super_admin_user(request.user):
            return self.list_display
        return ('user', 'role')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if _is_super_admin_user(request.user):
            return queryset
        return queryset

    def has_view_permission(self, request, obj=None):
        if _is_super_admin_user(request.user):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_change_permission(self, request, obj=None):
        if _is_super_admin_user(request.user):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_delete_permission(self, request, obj=None):
        if _is_super_admin_user(request.user):
            return True
        if obj is None:
            return False
        return bool(request.user and request.user.is_staff)

    def get_fieldsets(self, request, obj=None):
        if _is_super_admin_user(request.user):
            return super().get_fieldsets(request, obj)
        return (
            ('Asignación', {
                'fields': ('id', 'user', 'role'),
            }),
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user' and not _is_super_admin_user(request.user):
            kwargs['queryset'] = User.objects.filter(status='active', is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


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
        return _is_super_admin_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_add_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)
