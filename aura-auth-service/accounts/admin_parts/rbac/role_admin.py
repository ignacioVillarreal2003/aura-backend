"""Role admin configuration."""

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from accounts.models import Role, Permission, PermissionInRole
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.common import AuditedAdminMixin, is_super_admin_user, is_admin_or_super_user, log_audit, truncate_description, count_badge


class RoleAdminForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.order_by('name'),
        required=False,
        widget=FilteredSelectMultiple('Permisos', is_stacked=False),
        label='Permisos',
    )

    class Meta:
        model = Role
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['permissions'] = list(
                PermissionInRole.objects.filter(role=self.instance)
                .values_list('permission_id', flat=True)
            )


@admin.register(Role)
class RoleAdmin(AuditedAdminMixin, HelpTextStripMixin, admin.ModelAdmin):
    """Admin for Role model."""

    form = RoleAdminForm
    list_display = ('name', 'description_short', 'permission_count')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ('id',)
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description'),
        }),
        ('Permisos', {
            'fields': ('permissions',),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('name',)
        return self.readonly_fields

    def has_module_permission(self, request):
        return is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return is_admin_or_super_user(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        if not is_super_admin_user(request.user):
            return False
        if obj is None:
            return True
        if obj.name in ['superadmin', 'admin']:
            return False
        if request.user and obj.user_assignments.filter(
            user=request.user,
            deleted_at__isnull=True,
        ).exists():
            return False
        return True

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if 'permissions' not in form.cleaned_data:
            return
        selected = {p.pk for p in form.cleaned_data['permissions']}
        existing = set(
            PermissionInRole.objects.filter(role=form.instance)
            .values_list('permission_id', flat=True)
        )
        to_remove = existing - selected
        to_add = selected - existing
        if to_remove:
            PermissionInRole.objects.filter(role=form.instance, permission_id__in=to_remove).delete()
        for perm_id in to_add:
            PermissionInRole.objects.create(role=form.instance, permission_id=perm_id)

    def save_model(self, request, obj, form, change):
        actor, elevated_by = self._get_audit_actor(request)
        super().save_model(request, obj, form, change)
        details = {'changed_fields': form.changed_data} if change and form.changed_data else None
        log_audit(
            actor=actor,
            action='UPDATE' if change else 'CREATE',
            entity_type='role',
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
            entity_type='role',
            entity_id=obj.pk,
            entity_label=obj.name,
            elevated_by=elevated_by,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        if not (is_super_admin_user(request.user) or getattr(request, 'is_elevated', False)):
            return
        actor, elevated_by = self._get_audit_actor(request)
        protected = queryset.filter(
            name__in=['superadmin', 'admin']
        ) | queryset.filter(
            user_assignments__user=request.user,
            user_assignments__deleted_at__isnull=True,
        )
        safe_queryset = queryset.exclude(id__in=protected.values_list('id', flat=True))
        for obj in safe_queryset:
            log_audit(
                actor=actor,
                action='DELETE',
                entity_type='role',
                entity_id=obj.pk,
                entity_label=obj.name,
                elevated_by=elevated_by,
            )
        super().delete_queryset(request, safe_queryset)

    def description_short(self, obj):
        return truncate_description(obj.description)
    description_short.short_description = 'Descripción'

    def permission_count(self, obj):
        return count_badge(obj.permission_links.count())
    permission_count.short_description = 'Permisos'
