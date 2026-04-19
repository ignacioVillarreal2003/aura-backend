"""Permission admin configuration."""

from django.contrib import admin
from accounts.models import Permission
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.common import (
    AuditedAdminMixin,
    is_super_admin_user,
    is_admin_or_super_user,
    log_audit,
    truncate_description,
)


@admin.register(Permission)
class PermissionAdmin(AuditedAdminMixin, HelpTextStripMixin, admin.ModelAdmin):
    """Admin for Permission model."""

    list_display = ('name', 'description_short')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ()
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        return self.fieldsets

    def has_module_permission(self, request):
        return is_admin_or_super_user(request.user) or getattr(request, 'is_elevated', False)

    def has_view_permission(self, request, obj=None):
        return is_admin_or_super_user(request.user) or getattr(request, 'is_elevated', False)

    def has_add_permission(self, request):
        return is_super_admin_user(request.user) or getattr(request, 'is_elevated', False)

    def has_change_permission(self, request, obj=None):
        return is_super_admin_user(request.user) or getattr(request, 'is_elevated', False)

    def has_delete_permission(self, request, obj=None):
        return is_super_admin_user(request.user) or getattr(request, 'is_elevated', False)

    def description_short(self, obj):
        return truncate_description(obj.description)
    description_short.short_description = 'Descripción'

    def save_model(self, request, obj, form, change):
        actor, elevated_by = self._get_audit_actor(request)
        super().save_model(request, obj, form, change)
        details = {'changed_fields': form.changed_data} if change and form.changed_data else None
        log_audit(
            actor=actor,
            action='UPDATE' if change else 'CREATE',
            entity_type='permission',
            entity_id=obj.pk,
            entity_label=obj.name,
            details=details,
            elevated_by=elevated_by,
        )

    def delete_model(self, request, obj):
        actor, elevated_by = self._get_audit_actor(request)
        log_audit(
            actor=actor,
            action='DELETE',
            entity_type='permission',
            entity_id=obj.pk,
            entity_label=obj.name,
            elevated_by=elevated_by,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        actor, elevated_by = self._get_audit_actor(request)
        for obj in queryset:
            log_audit(
                actor=actor,
                action='DELETE',
                entity_type='permission',
                entity_id=obj.pk,
                entity_label=obj.name,
                elevated_by=elevated_by,
            )
        super().delete_queryset(request, queryset)
