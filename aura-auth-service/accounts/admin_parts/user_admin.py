"""User admin configuration."""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from accounts.models import User, Role, UserRole
from accounts.admin_parts.common import (
    StatusFilter,
    CreatedDateFilter,
    HelpTextStripMixin,
    _apply_audit_fields,
    _is_super_admin_user,
    _is_admin_or_super_user,
)
from accounts.admin_parts.forms.user_form import UserAdminForm


@admin.register(User)
class UserAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """
    Custom admin for User model.
    """

    class RoleFilter(admin.SimpleListFilter):
        title = 'Rol'
        parameter_name = 'rol'

        def lookups(self, request, model_admin):
            roles = Role.objects.order_by('name').values_list('name', flat=True)
            return [(name, name) for name in roles]

        def queryset(self, request, queryset):
            value = self.value()
            if not value:
                return queryset
            return queryset.filter(
                user_roles__role__name=value,
                user_roles__deleted_at__isnull=True,
            )

    list_display = (
        'username',
        'email',
        'roles_display',
        'status_badge',
        'created_date',
        'created_by_display',
        'last_login_display',
    )
    list_filter = (
        RoleFilter,
        StatusFilter,
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
        'last_password_change',
    )

    form = UserAdminForm
    actions = None
    actions_selection_counter = False

    fieldsets = (
        ('Identidad', {
            'fields': ('roles', 'username', 'email', 'password', 'active'),
        }),
        ('Grupos', {
            'fields': ('custom_groups',),
            'classes': ('groups-section',),
        }),
    )

    def status_badge(self, obj):
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">&#10007; Eliminado</span>'
            )
        if obj.status == 'active':
            return format_html(
                '<span style="color: green; font-weight: bold;">&#10003; Activo</span>'
            )
        return format_html(
            '<span style="color: #d96c6c; font-weight: bold;">&#x2753; Inactivo</span>'
        )
    status_badge.short_description = 'Estado'

    def roles_display(self, obj):
        roles = obj.user_roles.filter(deleted_at__isnull=True).values_list('role__name', flat=True)
        labels = []
        for role in roles:
            if role == 'ADMIN':
                labels.append('Administrador')
            elif role == 'USER':
                labels.append('Usuario')
            else:
                labels.append(role)
        return ', '.join(labels) if labels else '-'
    roles_display.short_description = 'Rol'

    def created_date(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y')
        return '-'
    created_date.short_description = 'Creado'
    created_date.admin_order_field = 'created_at'

    def created_by_display(self, obj):
        if obj.is_superuser and obj.created_by and obj.created_by.is_superuser:
            return 'Administracion'
        if obj.created_by:
            return obj.created_by.username
        return '-'
    created_by_display.short_description = 'Creado por'
    created_by_display.admin_order_field = 'created_by__username'

    def last_login_display(self, obj):
        if obj.last_login:
            return obj.last_login.strftime('%d/%m/%Y %H:%M')
        return '-'
    last_login_display.short_description = 'Ultimo login'
    last_login_display.admin_order_field = 'last_login'

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('username', 'email', 'roles_display')
        return self.readonly_fields

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.fieldsets
        if _is_super_admin_user(request.user):
            return (
                ('Identidad', {
                    'fields': ('roles_display', 'username', 'email', 'active'),
                }),
                ('Grupos', {
                    'fields': ('custom_groups',),
                }),
                ('Auditoría', {
                    'fields': (
                        'created_by',
                        'created_at',
                        'updated_by',
                        'updated_at',
                        'last_login',
                        'last_password_change',
                        'deleted_by',
                        'deleted_at',
                    ),
                }),
            )
        return (
            ('Identidad', {
                'fields': ('roles_display', 'username', 'email', 'active'),
            }),
            ('Grupos', {
                'fields': ('custom_groups',),
            }),
        )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field_name in ('created_by', 'updated_by', 'deleted_by'):
            if field_name in form.base_fields:
                form.base_fields.pop(field_name)
        for field_name in ('username', 'email'):
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = ''
        if obj:
            for field_name in ('roles', 'password'):
                if field_name in form.base_fields:
                    form.base_fields.pop(field_name)
            audit_labels = {
                'created_by': 'Creado por',
                'created_at': 'Fecha creado',
                'updated_by': 'Actualizado por',
                'updated_at': 'Fecha actualizado',
                'last_login': 'Ultimo inicio de sesion',
                'last_password_change': 'Ultimo cambio de contrasena',
                'deleted_by': 'Eliminado por',
                'deleted_at': 'Fecha eliminado',
            }
            for field_name, label in audit_labels.items():
                if field_name in form.base_fields:
                    form.base_fields[field_name].label = label
        if not _is_super_admin_user(request.user):
            if 'roles' in form.base_fields:
                form.base_fields['roles'].queryset = Role.objects.exclude(
                    name__in=['SUPER_ADMIN', 'ADMIN']
                )
        return form

    def get_list_filter(self, request):
        if _is_super_admin_user(request.user):
            return self.list_filter
        return (self.RoleFilter, StatusFilter, ('created_at', CreatedDateFilter))

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('user_roles__role').order_by('deleted_at', 'username')

    def has_add_permission(self, request):
        if _is_admin_or_super_user(request.user):
            return True
        return bool(request.user and request.user.is_staff)

    def has_module_permission(self, request):
        if _is_admin_or_super_user(request.user):
            return True
        return bool(request.user and request.user.is_staff)

    def has_view_permission(self, request, obj=None):
        if _is_admin_or_super_user(request.user):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_change_permission(self, request, obj=None):
        if _is_admin_or_super_user(request.user):
            return True
        if obj is None:
            return bool(request.user and request.user.is_staff)
        return bool(request.user and request.user.is_staff)

    def has_delete_permission(self, request, obj=None):
        if _is_admin_or_super_user(request.user):
            return True
        if obj is None:
            return False
        return bool(request.user and request.user.is_staff)

    filter_horizontal = ('custom_groups',)

    class Media:
        js = ('accounts/admin/user_password.js', 'accounts/admin/user_form.js')

        css = {
            "all": ("admin/custom.css",)
        }

    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        if 'active' in form.cleaned_data:
            obj.status = 'active' if form.cleaned_data['active'] else 'inactive'
        _apply_audit_fields(obj, request.user, is_create=not change)
        super().save_model(request, obj, form, change)
        if 'roles' in form.cleaned_data:
            selected_roles = []
            selected_role = form.cleaned_data['roles']
            if selected_role:
                selected_roles.append(selected_role)
            if not _is_super_admin_user(request.user):
                protected_roles = Role.objects.filter(
                    name__in=['SUPER_ADMIN', 'ADMIN'],
                    user_assignments__user=obj,
                    user_assignments__deleted_at__isnull=True,
                )
                for role in protected_roles:
                    if role not in selected_roles:
                        selected_roles.append(role)
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
