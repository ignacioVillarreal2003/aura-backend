"""Role admin configuration."""

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.html import format_html
from accounts.models import Role, Permission, PermissionInRole
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.utils.audit import _is_super_admin_user, _is_admin_or_super_user, _is_effective_superadmin, log_audit


class RoleAdminForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.order_by('name'),
        required=False,
        widget=FilteredSelectMultiple('Permisos', is_stacked=False),
        label='',
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
class RoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for Role model."""

    form = RoleAdminForm
    list_display = ('name', 'description_short', 'permission_count')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ()
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información del Rol', {
            'fields': ('name', 'description'),
        }),
        ('Permisos', {
            'fields': ('permissions',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        if not _is_effective_superadmin(request):
            return (
                ('Información del Rol', {
                    'fields': ('name', 'description'),
                }),
            )
        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('name', 'description')
        return ()

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        try:
            role = Role.objects.get(pk=object_id)
            extra_context['title'] = f'Rol - {role.name.capitalize()}'
            extra_context['subtitle'] = None
        except Role.DoesNotExist:
            pass
        return super().change_view(request, object_id, form_url, extra_context)

    def has_module_permission(self, request):
        return _is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_admin_or_super_user(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return _is_effective_superadmin(request)

    def has_delete_permission(self, request, obj=None):
        return False

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
        super().save_model(request, obj, form, change)
        action = 'UPDATE' if change else 'CREATE'
        details = {'changed_fields': form.changed_data} if change and form.changed_data else None
        log_audit(
            actor=request.user,
            action=action,
            entity_type='role',
            entity_id=obj.pk,
            entity_label=obj.name,
            details=details,
        )

    def delete_model(self, request, obj):
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='role',
            entity_id=obj.pk,
            entity_label=obj.name,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        if not _is_effective_superadmin(request):
            return
        protected = queryset.filter(
            name__in=['superadmin', 'admin']
        ) | queryset.filter(
            user_assignments__user=request.user,
            user_assignments__deleted_at__isnull=True,
        )
        safe_queryset = queryset.exclude(id__in=protected.values_list('id', flat=True))
        for obj in safe_queryset:
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='role',
                entity_id=obj.pk,
                entity_label=obj.name,
            )
        super().delete_queryset(request, safe_queryset)

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
