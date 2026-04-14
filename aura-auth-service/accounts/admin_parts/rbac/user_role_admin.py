"""User role admin configuration."""

from django.contrib import admin
from accounts.models import User, Role, UserRole
from accounts.admin_parts.utils.mixins import HelpTextStripMixin, HelpTextStripInlineMixin
from accounts.admin_parts.utils.audit import _is_super_admin_user, _is_admin_or_super_user, log_audit


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

    def has_module_permission(self, request):
        return False

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
        if _is_admin_or_super_user(request.user):
            return True
        return False

    def has_add_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

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
            kwargs['queryset'] = User.objects.filter(status='active', deleted_at__isnull=True)
        if db_field.name == 'role' and not _is_super_admin_user(request.user):
            kwargs['queryset'] = Role.objects.exclude(name__in=['superadmin', 'admin'])
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        action = 'UPDATE' if change else 'CREATE'
        log_audit(
            actor=request.user,
            action=action,
            entity_type='user_role',
            entity_id=obj.pk,
            entity_label=f'{obj.user} → {obj.role}',
        )

    def delete_model(self, request, obj):
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='user_role',
            entity_id=obj.pk,
            entity_label=f'{obj.user} → {obj.role}',
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='user_role',
                entity_id=obj.pk,
                entity_label=f'{obj.user} → {obj.role}',
            )
        super().delete_queryset(request, queryset)
