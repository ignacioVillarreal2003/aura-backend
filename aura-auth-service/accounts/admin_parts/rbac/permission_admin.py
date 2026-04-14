"""Permission admin configuration."""

from django.contrib import admin
from django.utils.html import format_html
from accounts.models import Permission, PermissionInRole, PermissionInFauRole
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.utils.audit import _is_super_admin_user, _is_admin_or_super_user, log_audit


class PermissionInRoleInline(admin.TabularInline):
    """Inline for assigning this permission to system roles."""

    model = PermissionInRole
    extra = 1
    can_delete = False
    fields = ('role',)
    verbose_name = 'Rol de sistema'
    verbose_name_plural = 'Roles de sistema asignados'

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_add_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return False


class PermissionInFauRoleInline(admin.TabularInline):
    """Inline for assigning this permission to FAU roles."""

    model = PermissionInFauRole
    extra = 1
    can_delete = False
    fields = ('fau_role',)
    verbose_name = 'Rol FAU'
    verbose_name_plural = 'Roles FAU asignados'

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_add_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Permission)
class PermissionAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for Permission model."""

    list_display = ('name', 'description_short', 'role_count', 'fau_role_count')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ()
    actions = None
    actions_selection_counter = False
    inlines = [PermissionInRoleInline, PermissionInFauRoleInline]

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        return self.fieldsets

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
    role_count.short_description = 'Roles sistema'

    def fau_role_count(self, obj):
        count = obj.fau_role_links.count()
        return format_html(
            '<span style="background-color: #6b8e23; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    fau_role_count.short_description = 'Roles FAU'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        action = 'UPDATE' if change else 'CREATE'
        details = {'changed_fields': form.changed_data} if change and form.changed_data else None
        log_audit(
            actor=request.user,
            action=action,
            entity_type='permission',
            entity_id=obj.pk,
            entity_label=obj.name,
            details=details,
        )

    def delete_model(self, request, obj):
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='permission',
            entity_id=obj.pk,
            entity_label=obj.name,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='permission',
                entity_id=obj.pk,
                entity_label=obj.name,
            )
        super().delete_queryset(request, queryset)
