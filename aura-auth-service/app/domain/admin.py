from django.contrib import admin
from .models import AuthUser, Role, AuthUserInRole, Permission, PermissionInRole


@admin.register(AuthUser)
class AuthUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'status', 'enabled', 'created_at')
    list_filter = ('status', 'enabled', 'created_at')
    search_fields = ('username', 'email')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('username', 'email', 'password', 'status')
        }),
        ('Account Status', {
            'fields': ('enabled', 'account_non_expired', 'account_non_locked', 'credentials_non_expired')
        }),
        ('Login Information', {
            'fields': ('last_login', 'failed_login_attempts', 'lockout_until')
        }),
        ('Password', {
            'fields': ('last_password_change', 'refresh_token')
        }),
        ('Audit Trail', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at', 'deleted_by', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(AuthUserInRole)
class AuthUserInRoleAdmin(admin.ModelAdmin):
    list_display = ('auth_user', 'role', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('auth_user__username', 'role__name')
    readonly_fields = ('created_at',)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(PermissionInRole)
class PermissionInRoleAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission')
    list_filter = ('role',)
    search_fields = ('role__name', 'permission__name')
