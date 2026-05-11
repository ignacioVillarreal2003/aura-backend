"""User admin configuration."""

from django.contrib import admin
from django.urls import reverse
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
    log_audit,
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
        'mac_profile_link',
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
            if role == 'user':
                labels.append('user')
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

    def mac_profile_link(self, obj):
        url = reverse('admin:mac_user_mac', args=[obj.pk])
        return format_html(
            '<a href="{}" style="'
            'display:inline-block;padding:3px 9px;background:#205067;color:#fff;'
            'border-radius:4px;font-size:11px;font-weight:600;text-decoration:none;'
            '">MAC</a>',
            url,
        )
    mac_profile_link.short_description = 'Perfil MAC'
    mac_profile_link.allow_tags = True

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
        if _is_super_admin_user(request.user):
            if 'roles' in form.base_fields:
                form.base_fields['roles'].queryset = Role.objects.exclude(name='superadmin')
        else:
            if 'roles' in form.base_fields:
                form.base_fields['roles'].queryset = Role.objects.exclude(
                    name__in=['superadmin', 'admin']
                )
        return form

    def get_list_filter(self, request):
        return self.list_filter

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return (
            queryset
            .filter(deleted_at__isnull=True)
            .prefetch_related('user_roles__role')
            .order_by('username')
        )

    def save_related(self, request, form, formsets, change):
        # custom_groups is a manual cross-DB form field (not a model field).
        # User lives in auth_db; auth_user_custom_groups lives in aura_db.
        # super() handles all other relations; we write those rows manually here.
        super().save_related(request, form, formsets, change)
        if 'custom_groups' not in form.cleaned_data:
            return
        from django.db import connections
        user_id = form.instance.pk
        selected_groups = list(form.cleaned_data['custom_groups'])
        with connections['aura_db'].cursor() as cursor:
            if selected_groups:
                group_ids = [str(g.pk) for g in selected_groups]
                placeholders = ','.join(['%s::uuid'] * len(group_ids))
                cursor.execute(
                    f'DELETE FROM auth_user_custom_groups '
                    f'WHERE user_id = %s AND customgroup_id NOT IN ({placeholders})',
                    [user_id] + group_ids,
                )
                for gid in group_ids:
                    cursor.execute(
                        'INSERT INTO auth_user_custom_groups (user_id, customgroup_id) '
                        'VALUES (%s, %s::uuid) ON CONFLICT DO NOTHING',
                        [user_id, gid],
                    )
            else:
                cursor.execute(
                    'DELETE FROM auth_user_custom_groups WHERE user_id = %s',
                    [user_id],
                )

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
        action = 'UPDATE' if change else 'CREATE'
        details = {'changed_fields': form.changed_data} if change and form.changed_data else None
        log_audit(
            actor=request.user,
            action=action,
            entity_type='auth_user',
            entity_id=obj.pk,
            entity_label=obj.username,
            details=details,
        )
        if 'roles' in form.cleaned_data:
            selected_roles = []
            selected_role = form.cleaned_data['roles']
            if selected_role:
                selected_roles.append(selected_role)
            if not _is_super_admin_user(request.user):
                protected_roles = Role.objects.filter(
                    name__in=['superadmin', 'admin'],
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
        # Soft-delete active role assignments before soft-deleting the user.
        UserRole.objects.filter(user=obj, deleted_at__isnull=True).update(
            deleted_at=timezone.now(),
            deleted_by_id=request.user.pk,
        )
        obj.soft_delete(deleted_by=request.user.pk)
        log_audit(
            actor=request.user,
            action='DELETE',
            entity_type='auth_user',
            entity_id=obj.pk,
            entity_label=obj.username,
        )

    def delete_queryset(self, request, queryset):
        now = timezone.now()
        for obj in queryset:
            UserRole.objects.filter(user=obj, deleted_at__isnull=True).update(
                deleted_at=now,
                deleted_by_id=request.user.pk,
            )
            obj.soft_delete(deleted_by=request.user.pk)
            log_audit(
                actor=request.user,
                action='DELETE',
                entity_type='auth_user',
                entity_id=obj.pk,
                entity_label=obj.username,
            )
