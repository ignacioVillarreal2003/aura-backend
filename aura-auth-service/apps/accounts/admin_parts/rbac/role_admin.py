"""Configuracion del admin de roles."""

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.html import format_html
from apps.accounts.models import Role, Permission, PermissionInRole
from apps.accounts.admin_parts.utils.mixins import HelpTextStripMixin
from apps.accounts.admin_parts.utils.audit import _is_super_admin_user, _is_admin_or_super_user, _is_effective_superadmin, log_audit
from apps.accounts.admin_parts.utils.permissions import has_permission


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
    """Admin del modelo Role."""

    form = RoleAdminForm
    list_display = ('name', 'description_short', 'permission_count', 'permissions_names')
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
        return has_permission(request, 'ADMIN_ROLES_VIEW')

    def has_view_permission(self, request, obj=None):
        return has_permission(request, 'ADMIN_ROLES_VIEW')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return has_permission(request, 'ADMIN_ROLES_EDIT') or _is_effective_superadmin(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_related(self, request, form, formsets, change):
        if 'permissions' not in form.cleaned_data:
            super().save_related(request, form, formsets, change)
            return

        selected = {p.pk for p in form.cleaned_data['permissions']}
        existing = set(
            PermissionInRole.objects.filter(role=form.instance)
            .values_list('permission_id', flat=True)
        )
        to_remove = existing - selected
        to_add = selected - existing

        super().save_related(request, form, formsets, change)

        if to_remove:
            PermissionInRole.objects.filter(role=form.instance, permission_id__in=to_remove).delete()
        for perm_id in to_add:
            PermissionInRole.objects.create(role=form.instance, permission_id=perm_id)

        if to_add or to_remove:
            added_names = list(
                Permission.objects.filter(pk__in=to_add).order_by('name').values_list('name', flat=True)
            )
            removed_names = list(
                Permission.objects.filter(pk__in=to_remove).order_by('name').values_list('name', flat=True)
            )
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='role_permissions',
                entity_id=form.instance.pk,
                entity_label=f'{request.user.username} actualizó permisos del rol {form.instance.name}',
                details={
                    'rol': form.instance.name,
                    'permisos_agregados': added_names,
                    'permisos_eliminados': removed_names,
                },
                request=request,
            )

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

    def permissions_names(self, obj):
        names = list(
            PermissionInRole.objects.filter(role=obj)
            .select_related('permission')
            .order_by('permission__name')
            .values_list('permission__name', flat=True)
        )
        if not names:
            return format_html('<span style="color:#bbb">—</span>')
        visible = names[:4]
        rest = names[4:]
        chips = ''.join(
            f'<span style="display:inline-block;background:#eef2f7;color:#1e3a5f;'
            f'border-radius:3px;padding:1px 6px;margin:1px;font-size:11px;">{n}</span>'
            for n in visible
        )
        if rest:
            chips += (
                f'<span title="{chr(10).join(rest)}" style="display:inline-block;background:#dde4ee;color:#444;'
                f'border-radius:3px;padding:1px 6px;margin:1px;font-size:11px;cursor:help;">'
                f'+{len(rest)} más</span>'
            )
        return format_html(chips)
    permissions_names.short_description = 'Lista de permisos'
    permissions_names.allow_tags = True
