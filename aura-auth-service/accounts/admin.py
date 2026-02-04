"""
Django Admin customization for RBAC models.

Features:
- Custom User admin with audit fields
- Role and Permission management
- UserRole and RolePermission inlines
- Soft delete handling
- Filtered views based on user roles
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import User, Role, Permission, UserRole, RolePermission


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Custom admin for User model.
    
    Features:
    - Display key user fields
    - Search by username and email
    - Filter by status and creation date
    - Show audit information
    - Prevent direct password editing (must use password field)
    """
    
    list_display = (
        'username',
        'email',
        'is_active_badge',
        'is_staff_badge',
        'created_at',
        'is_deleted_badge',
    )
    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
        'created_at',
        ('deleted_at', admin.EmptyFieldListFilter),
    )
    search_fields = ('username', 'email')
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
        'last_login',
    )
    
    fieldsets = (
        ('Identidad', {
            'fields': ('id', 'username', 'email'),
        }),
        ('Contraseña', {
            'fields': ('password',),
            'description': 'La contraseña se encripta automáticamente al guardar',
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Información de Auditoría', {
            'fields': (
                'created_at',
                'created_by',
                'updated_at',
                'updated_by',
                'deleted_at',
                'deleted_by',
                'last_login',
            ),
            'classes': ('collapse',),
        }),
    )

    def is_active_badge(self, obj):
        """Display active status as a colored badge."""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Activo</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Inactivo</span>'
        )
    is_active_badge.short_description = 'Estado'

    def is_staff_badge(self, obj):
        """Display staff status as a colored badge."""
        if obj.is_staff:
            return format_html(
                '<span style="color: blue; font-weight: bold;">Staff</span>'
            )
        return format_html('<span style="color: gray;">Usuario</span>')
    is_staff_badge.short_description = 'Tipo'

    def is_deleted_badge(self, obj):
        """Display soft delete status."""
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">Eliminado</span>'
            )
        return format_html('<span style="color: green;">Activo</span>')
    is_deleted_badge.short_description = 'Eliminado'

    def get_readonly_fields(self, request, obj=None):
        """
        Make certain fields read-only when editing existing users.
        """
        if obj:
            return self.readonly_fields + ('username', 'email')
        return self.readonly_fields


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin for Role model.
    
    Features:
    - Display role name and description
    - Search by name
    - Show audit fields
    - Inline permission assignment
    """
    
    list_display = ('name', 'description_short', 'permission_count', 'created_at', 'is_deleted_badge')
    list_filter = ('created_at', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('name', 'description')
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
    )
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description'),
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

    inlines = []  # Will add RolePermissionInline below

    def description_short(self, obj):
        """Display shortened description."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def permission_count(self, obj):
        """Display count of assigned permissions."""
        count = obj.role_permissions.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    permission_count.short_description = 'Permisos'

    def is_deleted_badge(self, obj):
        """Display soft delete status."""
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">Eliminado</span>'
            )
        return format_html('<span style="color: green;">Activo</span>')
    is_deleted_badge.short_description = 'Estado'


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    Admin for Permission model.
    
    Features:
    - Display permission code and description
    - Search by code
    - Show audit fields
    """
    
    list_display = ('code', 'description_short', 'role_count', 'created_at', 'is_deleted_badge')
    list_filter = ('created_at', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('code', 'description')
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
    )
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'code', 'description'),
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

    def description_short(self, obj):
        """Display shortened description."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def role_count(self, obj):
        """Display count of roles with this permission."""
        count = obj.permission_roles.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    role_count.short_description = 'Asignado a Roles'

    def is_deleted_badge(self, obj):
        """Display soft delete status."""
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">Eliminado</span>'
            )
        return format_html('<span style="color: green;">Activo</span>')
    is_deleted_badge.short_description = 'Estado'


class RolePermissionInline(admin.TabularInline):
    """Inline admin for assigning permissions to roles."""
    model = RolePermission
    extra = 1
    fields = ('permission', 'granted_at', 'granted_by')
    readonly_fields = ('granted_at', 'granted_by')
    verbose_name = 'Permiso'
    verbose_name_plural = 'Permisos'


class UserRoleInline(admin.TabularInline):
    """Inline admin for assigning roles to users."""
    model = UserRole
    extra = 1
    fields = ('role', 'assigned_at', 'assigned_by')
    readonly_fields = ('assigned_at', 'assigned_by')
    verbose_name = 'Rol'
    verbose_name_plural = 'Roles'


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """
    Admin for UserRole relationship.
    
    Features:
    - Display user and role assignment
    - Filter by role and user
    - Show assignment metadata
    """
    
    list_display = ('user', 'role', 'assigned_at', 'assigned_by')
    list_filter = ('role', 'assigned_at')
    search_fields = ('user__username', 'role__name')
    readonly_fields = ('id', 'assigned_at', 'assigned_by')
    
    fieldsets = (
        ('Asignación', {
            'fields': ('id', 'user', 'role'),
        }),
        ('Metadatos', {
            'fields': ('assigned_at', 'assigned_by'),
            'classes': ('collapse',),
        }),
    )


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """
    Admin for RolePermission relationship.
    
    Features:
    - Display role and permission assignment
    - Filter by role and permission
    - Show assignment metadata
    """
    
    list_display = ('role', 'permission', 'granted_at', 'granted_by')
    list_filter = ('role', 'granted_at')
    search_fields = ('role__name', 'permission__code')
    readonly_fields = ('id', 'granted_at', 'granted_by')
    
    fieldsets = (
        ('Asignación', {
            'fields': ('id', 'role', 'permission'),
        }),
        ('Metadatos', {
            'fields': ('granted_at', 'granted_by'),
            'classes': ('collapse',),
        }),
    )


# Customize admin site
admin.site.site_header = 'Administración'
admin.site.site_title = 'Admin Aura Auth'
admin.site.index_title = 'Panel de Administración'
