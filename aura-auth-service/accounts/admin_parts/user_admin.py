"""User admin configuration."""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from accounts.models import User, Role, FauRole
from django.core.exceptions import PermissionDenied
from accounts.admin_parts.common import (
    AuditedAdminMixin,
    StatusFilter,
    CreatedDateFilter,
    HelpTextStripMixin,
    apply_audit_fields,
    is_super_admin_user,
    is_admin_or_super_user,
    log_audit,
)
from accounts.admin_parts.forms.user_form import UserAdminForm
from accounts.repositories import group_membership as gm_repo
from accounts.services.user_service import assign_roles_to_user


@admin.register(User)
class UserAdmin(AuditedAdminMixin, HelpTextStripMixin, admin.ModelAdmin):
    """Custom admin for User model."""

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
        'fau_role_display',
        'status_badge',
        'created_date',
        'created_by_display',
        'last_login_display',
    )
    list_filter = (
        RoleFilter,
        ('fau_role', admin.RelatedOnlyFieldListFilter),
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
        ('Rol FAU', {
            'fields': ('fau_role',),
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
        return ', '.join(roles) if roles else '-'
    roles_display.short_description = 'Rol'

    def fau_role_display(self, obj):
        if obj.fau_role:
            return obj.fau_role.name
        return '-'
    fau_role_display.short_description = 'Rol FAU'
    fau_role_display.admin_order_field = 'fau_role__name'

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
        fau_section = ('Rol FAU', {'fields': ('fau_role',)})
        if is_super_admin_user(request.user):
            return (
                ('Identidad', {
                    'fields': ('roles_display', 'username', 'email', 'active'),
                }),
                ('Grupos', {
                    'fields': ('custom_groups',),
                }),
                fau_section,
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
            fau_section,
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
        if is_super_admin_user(request.user):
            if 'roles' in form.base_fields:
                form.base_fields['roles'].queryset = Role.objects.exclude(name='superadmin')
        else:
            if 'roles' in form.base_fields:
                form.base_fields['roles'].queryset = Role.objects.exclude(
                    name__in=['superadmin', 'admin']
                )
        if 'fau_role' in form.base_fields:
            form.base_fields['fau_role'].queryset = FauRole.objects.order_by('-power', 'name')
        return form

    def get_list_filter(self, request):
        if is_super_admin_user(request.user):
            return self.list_filter
        return (self.RoleFilter, StatusFilter, ('created_at', CreatedDateFilter))

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .filter(deleted_at__isnull=True)
            .prefetch_related('user_roles__role')
            .order_by('username')
        )

    def save_related(self, request, form, formsets, change):
        # custom_groups is a manual cross-DB form field (not a model field).
        # User lives in auth_db; auth_user_custom_groups lives in aura_db.
        super().save_related(request, form, formsets, change)
        if 'custom_groups' not in form.cleaned_data:
            return
        user_id = form.instance.pk
        selected_groups = list(form.cleaned_data['custom_groups'])
        group_ids = [str(g.pk) for g in selected_groups]
        gm_repo.set_groups_for_user(user_id, group_ids)

    def has_add_permission(self, request):
        if is_admin_or_super_user(request.user):
            return True
        return bool(request.user and request.user.is_staff)

    def has_module_permission(self, request):
        if is_admin_or_super_user(request.user):
            return True
        return bool(request.user and request.user.is_staff)

    def has_view_permission(self, request, obj=None):
        if is_admin_or_super_user(request.user):
            return True
        return bool(request.user and request.user.is_staff)

    def has_change_permission(self, request, obj=None):
        if is_admin_or_super_user(request.user):
            return True
        return bool(request.user and request.user.is_staff)

    def has_delete_permission(self, request, obj=None):
        if is_admin_or_super_user(request.user):
            return True
        if obj is None:
            return False
        return bool(request.user and request.user.is_staff)

    class Media:
        js = ('accounts/admin/user_password.js', 'accounts/admin/user_form.js')
        css = {'all': ('admin/custom.css',)}

    def save_model(self, request, obj, form, change):
        actor, elevated_by = self._get_audit_actor(request)
        selected_role = form.cleaned_data.get('roles') if 'roles' in form.cleaned_data else None
        if selected_role and selected_role.name in ('admin', 'superadmin'):
            if not (is_super_admin_user(request.user) or getattr(request, 'is_elevated', False)):
                raise PermissionDenied('No tenés permiso para asignar este rol.')
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        if 'active' in form.cleaned_data:
            obj.status = 'active' if form.cleaned_data['active'] else 'inactive'
        apply_audit_fields(obj, request.user, is_create=not change)
        super().save_model(request, obj, form, change)
        log_audit(
            actor=actor,
            action='UPDATE' if change else 'CREATE',
            entity_type='auth_user',
            entity_id=obj.pk,
            entity_label=obj.username,
            details={'changed_fields': form.changed_data} if change and form.changed_data else None,
            elevated_by=elevated_by,
        )
        if 'roles' in form.cleaned_data:
            assign_roles_to_user(
                user=obj,
                selected_role=form.cleaned_data['roles'],
                actor=request.user,
                protect_system_roles=not (is_super_admin_user(request.user) or getattr(request, 'is_elevated', False)),
            )

    def delete_model(self, request, obj):
        from accounts.models import UserRole
        actor, elevated_by = self._get_audit_actor(request)
        UserRole.objects.filter(user=obj, deleted_at__isnull=True).update(
            deleted_at=timezone.now(),
            deleted_by_id=request.user.pk,
        )
        obj.soft_delete(deleted_by=request.user.pk)
        log_audit(
            actor=actor,
            action='DELETE',
            entity_type='auth_user',
            entity_id=obj.pk,
            entity_label=obj.username,
            elevated_by=elevated_by,
        )

    def delete_queryset(self, request, queryset):
        from accounts.models import UserRole
        actor, elevated_by = self._get_audit_actor(request)
        now = timezone.now()
        for obj in queryset:
            UserRole.objects.filter(user=obj, deleted_at__isnull=True).update(
                deleted_at=now,
                deleted_by_id=request.user.pk,
            )
            obj.soft_delete(deleted_by=request.user.pk)
            log_audit(
                actor=actor,
                action='DELETE',
                entity_type='auth_user',
                entity_id=obj.pk,
                entity_label=obj.username,
                elevated_by=elevated_by,
            )
