"""Configuracion del admin de permisos."""

from django.contrib import admin
from apps.accounts.models import Permission
from apps.accounts.admin_parts.utils.mixins import HelpTextStripMixin
from apps.accounts.admin_parts.utils.audit import _is_super_admin_user, _is_admin_or_super_user, log_audit
from apps.accounts.admin_parts.utils.permissions import has_permission


@admin.register(Permission)
class PermissionAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin del modelo Permission."""

    change_form_template = 'admin/accounts/permission/change_form.html'

    list_display = ('name', 'description_short')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ('name', 'description')
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
        return has_permission(request, 'ADMIN_ROLES_VIEW')

    def has_view_permission(self, request, obj=None):
        return has_permission(request, 'ADMIN_ROLES_VIEW')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            perm = Permission.objects.get(pk=object_id)
            extra_context['title'] = f'Permiso - {perm.name}'
            extra_context['subtitle'] = None
        except Permission.DoesNotExist:
            pass
        return super().change_view(request, object_id, form_url, extra_context)

    def description_short(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

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
