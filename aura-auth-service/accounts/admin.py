"""
Django Admin customization for RBAC models.

Features:
- Custom User admin with audit fields
- Role and Permission management
- UserRole and PermissionInRole inlines
- Soft delete handling
- Filtered views based on user roles
"""

from django.contrib import admin
from django import forms
from django.contrib.auth.models import Group
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.html import format_html
from .models import User, Role, Permission, UserRole, PermissionInRole, CustomGroup


class StatusFilter(admin.SimpleListFilter):
    title = 'Estado'
    parameter_name = 'estado'

    def lookups(self, request, model_admin):
        return (
            ('activo', 'Activo'),
            ('inactivo', 'Inactivo'),
            ('eliminado', 'Eliminado'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'activo':
            return queryset.filter(status='active', is_active=True, deleted_at__isnull=True)
        if value == 'inactivo':
            return queryset.filter(status='inactive', deleted_at__isnull=True)
        if value == 'eliminado':
            return queryset.filter(deleted_at__isnull=False)
        return queryset


class EnabledFilter(admin.SimpleListFilter):
    title = 'Habilitado'
    parameter_name = 'enabled'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Habilitado'),
            ('0', 'Deshabilitado'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == '1':
            return queryset.filter(is_active=True)
        if value == '0':
            return queryset.filter(is_active=False)
        return queryset


class CreatedDateFilter(admin.DateFieldListFilter):
    title = 'Creado'


def _apply_audit_fields(obj, user: User, is_create: bool):
    if is_create and not obj.created_by:
        obj.created_by = user
    obj.updated_by = user


def _is_super_admin_user(user: User) -> bool:
    return bool(user and user.is_superuser)


class HelpTextStripMixin:
    """Remove help text from admin forms."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield


class HelpTextStripInlineMixin:
    """Remove help text from inline admin forms."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield:
            formfield.help_text = ''
        return formfield


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
    
    Features:
    - Display key user fields
    - Search by username and email
    - Filter by status and creation date
    - Show audit information
    - Prevent direct password editing (must use password field)
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
        """Display status with soft delete handling."""
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
        """Display enabled status as a colored badge."""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">Habilitado</span>'
            )
        return format_html('<span style="color: gray;">Deshabilitado</span>')
    enabled_badge.short_description = 'Habilitado'

    def created_date(self, obj):
        """Display created date in dd/mm/aaaa format."""
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y')
        return '-'
    created_date.short_description = 'Creado'
    created_date.admin_order_field = 'created_at'

    def get_readonly_fields(self, request, obj=None):
        """
        Make certain fields read-only when editing existing users.
        """
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
        if not _is_super_admin_user(request.user):
            for field_name in ('custom_groups',):
                if field_name in form.base_fields:
                    form.base_fields.pop(field_name)
        return form

    def get_list_filter(self, request):
        if _is_super_admin_user(request.user):
            return self.list_filter
        return (StatusFilter, ('created_at', CreatedDateFilter))

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if _is_super_admin_user(request.user):
            return queryset.order_by('deleted_at', 'username')
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


@admin.register(Role)
class RoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """
    Admin for Role model.
    
    Features:
    - Display role name and description
    - Search by name
    - Show audit fields
    - Inline permission assignment
    """
    
    list_display = ('name', 'description_short', 'permission_count')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ('id',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description'),
        }),
    )

    inlines = []  # Will add PermissionInRoleInline below

    def has_module_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_add_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def description_short(self, obj):
        """Display shortened description."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def permission_count(self, obj):
        """Display count of assigned permissions."""
        count = obj.permission_links.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    permission_count.short_description = 'Permisos'


@admin.register(Permission)
class PermissionAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """
    Admin for Permission model.
    
    Features:
    - Display permission code and description
    - Search by code
    - Show audit fields
    """
    
    list_display = ('name', 'description_short', 'role_count')
    list_filter = ()
    search_fields = ('name', 'description')
    readonly_fields = ('id',)
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description'),
        }),
    )

    def has_module_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_add_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def description_short(self, obj):
        """Display shortened description."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def role_count(self, obj):
        """Display count of roles with this permission."""
        count = obj.role_links.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    role_count.short_description = 'Asignado a Roles'


class PermissionInRoleInline(HelpTextStripInlineMixin, admin.TabularInline):
    """Inline admin for assigning permissions to roles."""
    model = PermissionInRole
    extra = 1
    fields = ('permission',)
    verbose_name = 'Permiso'
    verbose_name_plural = 'Permisos'


RoleAdmin.inlines = [PermissionInRoleInline]


class UserRoleInline(HelpTextStripInlineMixin, admin.TabularInline):
    """Inline admin for assigning roles to users."""
    model = UserRole
    extra = 1
    fields = ('role', 'created_at', 'created_by', 'deleted_at', 'deleted_by')
    readonly_fields = ('created_at', 'created_by', 'deleted_at', 'deleted_by')
    verbose_name = 'Rol'
    verbose_name_plural = 'Roles'




@admin.register(UserRole)
class UserRoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """
    Admin for UserRole relationship.
    
    Features:
    - Display user and role assignment
    - Filter by role and user
    - Show assignment metadata
    """
    
    list_display = ('user', 'role', 'created_at', 'created_by', 'deleted_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__username', 'role__name')
    readonly_fields = ('id', 'created_at', 'created_by', 'deleted_at', 'deleted_by')
    
    fieldsets = (
        ('Asignación', {
            'fields': ('id', 'user', 'role'),
        }),
        ('Metadatos', {
            'fields': ('created_at', 'created_by', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',),
        }),
    )

    def get_list_display(self, request):
        if _is_super_admin_user(request.user):
            return self.list_display
        return ('user', 'role')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if _is_super_admin_user(request.user):
            return queryset
        return queryset

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

    def get_fieldsets(self, request, obj=None):
        if _is_super_admin_user(request.user):
            return super().get_fieldsets(request, obj)
        return (
            ('Asignación', {
                'fields': ('id', 'user', 'role'),
            }),
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user' and not _is_super_admin_user(request.user):
            kwargs['queryset'] = User.objects.filter(status='active', is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PermissionInRole)
class PermissionInRoleAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """
    Admin for PermissionInRole relationship.
    """

    list_display = ('role', 'permission')
    list_filter = ('role',)
    search_fields = ('role__name', 'permission__name')
    readonly_fields = ('id',)

    fieldsets = (
        ('Asignación', {
            'fields': ('id', 'role', 'permission'),
        }),
    )

    def has_module_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_add_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)


# Customize admin site
admin.site.site_header = 'Administración'
admin.site.site_title = 'Admin Aura Auth'
admin.site.index_title = 'Panel de Administración'

# Unregister Group from Django auth
admin.site.unregister(Group)

# Register custom groups under accounts app
@admin.register(CustomGroup)
class CustomGroupAdmin(HelpTextStripMixin, admin.ModelAdmin):
    """
    Custom admin for Group model to manage groups.
    """
    list_display = ('name', 'description_short', 'document_count', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('documents',)

    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description', 'documents'),
        }),
        ('Información de Auditoría', {
            'fields': (
                'created_at',
                'created_by',
                'updated_at',
                'updated_by',
                'deleted_at',
                'deleted_by',
            ),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
    )

    def description_short(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def document_count(self, obj):
        count = obj.documents.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    document_count.short_description = 'Documentos'

    def has_module_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_view_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_add_permission(self, request):
        return _is_super_admin_user(request.user)

    def has_change_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def has_delete_permission(self, request, obj=None):
        return _is_super_admin_user(request.user)

    def save_model(self, request, obj, form, change):
        _apply_audit_fields(obj, request.user.username, is_create=not change)
        super().save_model(request, obj, form, change)


def _custom_get_app_list(self, request):
    """
    Custom ordering for models in the admin index.
    """
    app_list = admin.AdminSite.get_app_list(self, request)
    desired_order = ['User', 'UserRole']
    if _is_super_admin_user(request.user):
        desired_order = [
            'User',
            'CustomGroup',
            'Role',
            'UserRole',
            'Permission',
            'PermissionInRole',
        ]
    order_map = {name: index for index, name in enumerate(desired_order)}

    documents_order = ['Document', 'DocumentRole']
    documents_order_map = {name: index for index, name in enumerate(documents_order)}

    app_order = {
        'accounts': 0,
        'documents': 1,
    }

    for app in app_list:
        if app.get('app_label') == 'accounts':
            if not _is_super_admin_user(request.user):
                app['models'] = [
                    model for model in app['models']
                    if model.get('object_name') in {'User', 'UserRole'}
                ]
            app['models'].sort(
                key=lambda model: order_map.get(model.get('object_name'), len(order_map))
            )
        if app.get('app_label') == 'documents':
            app['models'].sort(
                key=lambda model: documents_order_map.get(
                    model.get('object_name'),
                    len(documents_order_map)
                )
            )
    app_list.sort(
        key=lambda app: app_order.get(app.get('app_label'), len(app_order))
    )
    return app_list


admin.site.get_app_list = _custom_get_app_list.__get__(admin.site, admin.AdminSite)
