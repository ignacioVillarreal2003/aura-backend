"""User admin configuration."""

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils import timezone
from django.utils.html import format_html
from accounts.models import User, Role, UserRole, CustomGroup
from accounts.admin_parts.common import (
    StatusFilter,
    EnabledFilter,
    CreatedDateFilter,
    HelpTextStripMixin,
    _apply_audit_fields,
    _is_super_admin_user,
)


class UserAdminForm(forms.ModelForm):
    custom_groups = forms.ModelMultipleChoiceField(
        queryset=CustomGroup.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('Grupos', is_stacked=False),
        label='',
        help_text='',
    )

    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('Roles', is_stacked=False),
        label='',
    )

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if 'roles' in self.fields:
                self.fields['roles'].initial = Role.objects.filter(user_assignments__user=self.instance)
            if 'custom_groups' in self.fields:
                self.fields['custom_groups'].initial = self.instance.custom_groups.all()


@admin.register(User)
class UserAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """
    Custom admin for User model.
    """

    list_display = (
        'username',
        'email',
        'status_badge',
        'enabled_badge',
        'created_date',
    )
    list_filter = (
        StatusFilter,
        EnabledFilter,
        ('created_at', CreatedDateFilter),
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

    form = UserAdminForm
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Identidad', {
            'fields': ('id', 'username', 'email'),
        }),
        ('Contraseña', {
            'fields': ('password',),
            'description': 'La contraseña se encripta automáticamente al guardar',
        }),
        ('Estado y Seguridad', {
            'fields': (
                'status',
                'is_active',
                'account_non_expired',
                'account_non_locked',
                'credentials_non_expired',
                'failed_login_attempts',
                'lockout_until',
                'last_password_change',
            ),
        }),
        ('Grupos y Roles', {
            'fields': ('custom_groups', 'roles'),
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

    def status_badge(self, obj):
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">Eliminado</span>'
            )
        if obj.status == 'active':
            return format_html(
                '<span style="color: green; font-weight: bold;">Activo</span>'
            )
        return format_html(
            '<span style="color: orange; font-weight: bold;">Inactivo</span>'
        )
    status_badge.short_description = 'Estado'

    def enabled_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">Habilitado</span>'
            )
        return format_html('<span style="color: gray;">Deshabilitado</span>')
    enabled_badge.short_description = 'Habilitado'

    def created_date(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y')
        return '-'
    created_date.short_description = 'Creado'
    created_date.admin_order_field = 'created_at'

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('username', 'email')
        return self.readonly_fields

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            if not _is_super_admin_user(request.user):
                return (
                    ('Identidad', {
                        'fields': ('id', 'username', 'email'),
                    }),
                    ('Contraseña', {
                        'fields': ('password',),
                        'description': 'La contraseña se encripta automáticamente al guardar',
                    }),
                    ('Roles', {
                        'fields': ('roles',),
                    }),
                )
            return (
                ('Identidad', {
                    'fields': ('id', 'username', 'email'),
                }),
                ('Contraseña', {
                    'fields': ('password',),
                    'description': 'La contraseña se encripta automáticamente al guardar',
                }),
                ('Estado y Seguridad', {
                    'fields': (
                        'status',
                        'is_active',
                        'account_non_expired',
                        'account_non_locked',
                        'credentials_non_expired',
                        'failed_login_attempts',
                        'lockout_until',
                        'last_password_change',
                    ),
                }),
                ('Grupos y Roles', {
                    'fields': ('custom_groups', 'roles'),
                }),
            )
        if _is_super_admin_user(request.user):
            return (
                ('Identidad', {
                    'fields': ('id', 'username', 'email'),
                }),
                ('Estado y Seguridad', {
                    'fields': (
                        'status',
                        'is_active',
                        'account_non_expired',
                        'account_non_locked',
                        'credentials_non_expired',
                        'failed_login_attempts',
                        'lockout_until',
                        'last_password_change',
                    ),
                }),
                ('Grupos y Roles', {
                    'fields': ('custom_groups', 'roles'),
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
        return (
            ('Identidad', {
                'fields': ('id', 'username', 'email'),
            }),
            ('Roles', {
                'fields': ('roles',),
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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field_name in ('created_by', 'updated_by', 'deleted_by'):
            if field_name in form.base_fields:
                form.base_fields.pop(field_name)
        if not _is_super_admin_user(request.user):
            for field_name in ('custom_groups',):
                if field_name in form.base_fields:
                    form.base_fields.pop(field_name)
            if 'roles' in form.base_fields:
                form.base_fields['roles'].queryset = Role.objects.exclude(
                    name__in=['SUPER_ADMIN', 'ADMIN']
                )
        return form

    def get_list_filter(self, request):
        if _is_super_admin_user(request.user):
            return self.list_filter
        return (StatusFilter, ('created_at', CreatedDateFilter))

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.order_by('deleted_at', 'username')

    def has_add_permission(self, request):
        if _is_super_admin_user(request.user):
            return True
        return bool(request.user and request.user.is_staff)

    def has_view_permission(self, request, obj=None):
        if _is_super_admin_user(request.user):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_change_permission(self, request, obj=None):
        if _is_super_admin_user(request.user):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_delete_permission(self, request, obj=None):
        if _is_super_admin_user(request.user):
            return True
        if obj is None:
            return False
        return bool(request.user and request.user.is_staff)

    filter_horizontal = ('custom_groups',)

    class Media:
        js = ('accounts/admin/user_password.js',)

        css = {
            "all": ("admin/custom.css",)
        }

    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        _apply_audit_fields(obj, request.user, is_create=not change)
        super().save_model(request, obj, form, change)
        if 'roles' in form.cleaned_data:
            selected_roles = form.cleaned_data['roles']
            UserRole.objects.filter(
                user=obj,
                deleted_at__isnull=True,
            ).exclude(role__in=selected_roles).update(
                deleted_at=timezone.now(),
                deleted_by=request.user,
            )
            existing_roles = set(
                UserRole.objects.filter(user=obj, deleted_at__isnull=True)
                .values_list('role_id', flat=True)
            )
            to_create = [
                UserRole(user=obj, role=role, created_by=request.user)
                for role in selected_roles
                if role.id not in existing_roles
            ]
            if to_create:
                UserRole.objects.bulk_create(to_create)

    def delete_model(self, request, obj):
        obj.soft_delete(deleted_by=request.user)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.soft_delete(deleted_by=request.user)
