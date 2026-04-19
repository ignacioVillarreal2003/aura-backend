"""FAU role admin configuration."""

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.html import format_html
from accounts.models import FauRole, PermissionInFauRole, Permission
from accounts.admin_parts.utils.mixins import HelpTextStripMixin
from accounts.admin_parts.common import is_admin_or_super_user, is_super_admin_user, log_audit


class FauRoleAdminForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.order_by('name'),
        required=False,
        widget=FilteredSelectMultiple('Permisos', is_stacked=False),
        label='Permisos',
    )

    class Meta:
        model = FauRole
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial['permissions'] = list(
                PermissionInFauRole.objects.filter(fau_role=self.instance)
                .values_list('permission_id', flat=True)
            )


@admin.register(FauRole)
class FauRoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """Admin for FauRole model."""

    form = FauRoleAdminForm
    list_display = ('name', 'power_badge', 'description')
    search_fields = ('name', 'description')
    readonly_fields = ()
    ordering = ('-power',)
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description'),
        }),
        ('Jerarquía', {
            'fields': ('power',),
            'description': (
                'El nivel de poder define la jerarquía entre roles FAU. '
                'Mayor número = mayor poder. Debe ser único.'
            ),
        }),
        ('Permisos', {
            'fields': ('permissions',),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('name',)
        return self.readonly_fields

    def power_badge(self, obj):
        if obj.power is not None:
            return format_html(
                '<span style="background-color: #417690; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">{}</span>',
                obj.power,
            )
        return format_html('<span style="color: #999;">-</span>')
    power_badge.short_description = 'Nivel Jerárquico'
    power_badge.admin_order_field = 'power'

    def has_module_permission(self, request):
        return is_admin_or_super_user(request.user)

    def has_view_permission(self, request, obj=None):
        return is_admin_or_super_user(request.user)

    def has_add_permission(self, request):
        return is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_super_admin_user(request.user)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if 'permissions' not in form.cleaned_data:
            return
        selected = {p.pk for p in form.cleaned_data['permissions']}
        existing = set(
            PermissionInFauRole.objects.filter(fau_role=form.instance)
            .values_list('permission_id', flat=True)
        )
        to_remove = existing - selected
        to_add = selected - existing
        if to_remove:
            PermissionInFauRole.objects.filter(
                fau_role=form.instance, permission_id__in=to_remove
            ).delete()
        for perm_id in to_add:
            PermissionInFauRole.objects.create(fau_role=form.instance, permission_id=perm_id)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        action = 'UPDATE' if change else 'CREATE'
        details = {'changed_fields': form.changed_data} if change and form.changed_data else None
        log_audit(
            actor=request.user,
            action=action,
            entity_type='fau_role',
            entity_id=obj.pk,
            entity_label=obj.name,
            details=details,
        )

    def delete_model(self, request, obj):
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='fau_role',
            entity_id=obj.pk,
            entity_label=obj.name,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='fau_role',
                entity_id=obj.pk,
                entity_label=obj.name,
            )
        super().delete_queryset(request, queryset)
