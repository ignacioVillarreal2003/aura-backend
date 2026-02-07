"""
Django Admin customization for RBAC models.

Features:
- Custom User admin with audit fields
- Role and Permission management
- UserRole and RolePermission inlines
- Soft delete handling
- Filtered views based on user roles
"""

from django.contrib import admin
from django import forms
from django.contrib.auth.models import Group
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import User, Role, Permission, UserRole, RolePermission, GroupProxy


class ActiveFilter(admin.SimpleListFilter):
    title = 'Activo'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Sí'),
            ('0', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == '1':
            return queryset.filter(is_active=True)
        if value == '0':
            return queryset.filter(is_active=False)
        return queryset


class StaffFilter(admin.SimpleListFilter):
    title = 'Staff'
    parameter_name = 'is_staff'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Sí'),
            ('0', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == '1':
            return queryset.filter(is_staff=True)
        if value == '0':
            return queryset.filter(is_staff=False)
        return queryset


class CreatedDateFilter(admin.DateFieldListFilter):
    title = 'Creado'


def _apply_audit_fields(obj, username: str, is_create: bool):
    if is_create and not obj.created_by:
        obj.created_by = username
    obj.updated_by = username


class UserAdminForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('Grupos', is_stacked=False),
        label='',
        help_text='Grupos disponibles → Grupos Elegidos',
    )
    
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        required=False,
        widget=FilteredSelectMultiple('Roles', is_stacked=False),
        label='Roles',
    )

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['roles'].initial = Role.objects.filter(user_assignments__user=self.instance)
            self.fields['groups'].initial = self.instance.groups.all()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
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
        'is_active_badge',
        'is_staff_badge',
        'created_date',
    )
    list_filter = (
        ActiveFilter,
        StaffFilter,
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

    fieldsets = (
        ('Identidad', {
            'fields': ('id', 'username', 'email'),
        }),
        ('Contraseña', {
            'fields': ('password',),
            'description': 'La contraseña se encripta automáticamente al guardar',
        }),
        ('Grupos y Roles', {
            'fields': ('is_active', 'is_staff', 'groups', 'roles'),
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

    def is_active_badge(self, obj):
        """Display active status as a colored badge."""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Activo</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Inactivo</span>'
        )
    is_active_badge.short_description = 'Estado'

    def is_staff_badge(self, obj):
        """Display staff status as a colored badge."""
        if obj.is_staff:
            return format_html(
                '<span style="color: blue; font-weight: bold;">Staff</span>'
            )
        return format_html('<span style="color: gray;">Usuario</span>')
    is_staff_badge.short_description = 'Tipo'

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

    filter_horizontal = ('groups',)

    class Media:
        js = ('accounts/admin/user_password.js',)

    def save_model(self, request, obj, form, change):
        _apply_audit_fields(obj, request.user.username, is_create=not change)
        super().save_model(request, obj, form, change)
        if 'roles' in form.cleaned_data:
            selected_roles = form.cleaned_data['roles']
            UserRole.objects.filter(user=obj).exclude(role__in=selected_roles).delete()
            existing_roles = set(UserRole.objects.filter(user=obj).values_list('role_id', flat=True))
            to_create = [
                UserRole(user=obj, role=role, assigned_by=request.user.username)
                for role in selected_roles
                if role.id not in existing_roles
            ]
            if to_create:
                UserRole.objects.bulk_create(to_create)

    def delete_model(self, request, obj):
        obj.soft_delete(deleted_by=request.user.username)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            obj.soft_delete(deleted_by=request.user.username)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin for Role model.
    
    Features:
    - Display role name and description
    - Search by name
    - Show audit fields
    - Inline permission assignment
    """
    
    list_display = ('name', 'description_short', 'permission_count', 'created_at', 'is_deleted_badge')
    list_filter = ('created_at', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('name', 'description')
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
    )
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description'),
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

    inlines = []  # Will add RolePermissionInline below

    def save_model(self, request, obj, form, change):
        _apply_audit_fields(obj, request.user.username, is_create=not change)
        super().save_model(request, obj, form, change)

    def description_short(self, obj):
        """Display shortened description."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def permission_count(self, obj):
        """Display count of assigned permissions."""
        count = obj.role_permissions.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    permission_count.short_description = 'Permisos'

    def is_deleted_badge(self, obj):
        """Display soft delete status."""
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">Eliminado</span>'
            )
        return format_html('<span style="color: green;">Activo</span>')
    is_deleted_badge.short_description = 'Estado'


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    Admin for Permission model.
    
    Features:
    - Display permission code and description
    - Search by code
    - Show audit fields
    """
    
    list_display = ('code', 'description_short', 'role_count', 'created_at', 'is_deleted_badge')
    list_filter = ('created_at', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('code', 'description')
    readonly_fields = (
        'id',
        'created_at',
        'created_by',
        'updated_at',
        'updated_by',
        'deleted_at',
        'deleted_by',
    )
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'code', 'description'),
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

    def save_model(self, request, obj, form, change):
        _apply_audit_fields(obj, request.user.username, is_create=not change)
        super().save_model(request, obj, form, change)

    def description_short(self, obj):
        """Display shortened description."""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Descripción'

    def role_count(self, obj):
        """Display count of roles with this permission."""
        count = obj.permission_roles.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    role_count.short_description = 'Asignado a Roles'

    def is_deleted_badge(self, obj):
        """Display soft delete status."""
        if obj.is_deleted:
            return format_html(
                '<span style="color: red; font-weight: bold;">Eliminado</span>'
            )
        return format_html('<span style="color: green;">Activo</span>')
    is_deleted_badge.short_description = 'Estado'


class RolePermissionInline(admin.TabularInline):
    """Inline admin for assigning permissions to roles."""
    model = RolePermission
    extra = 1
    fields = ('permission', 'granted_at', 'granted_by')
    readonly_fields = ('granted_at', 'granted_by')
    verbose_name = 'Permiso'
    verbose_name_plural = 'Permisos'


class UserRoleInline(admin.TabularInline):
    """Inline admin for assigning roles to users."""
    model = UserRole
    extra = 1
    fields = ('role', 'assigned_at', 'assigned_by')
    readonly_fields = ('assigned_at', 'assigned_by')
    verbose_name = 'Rol'
    verbose_name_plural = 'Roles'




@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """
    Admin for UserRole relationship.
    
    Features:
    - Display user and role assignment
    - Filter by role and user
    - Show assignment metadata
    """
    
    list_display = ('user', 'role', 'assigned_at', 'assigned_by')
    list_filter = ('role', 'assigned_at')
    search_fields = ('user__username', 'role__name')
    readonly_fields = ('id', 'assigned_at', 'assigned_by')
    
    fieldsets = (
        ('Asignación', {
            'fields': ('id', 'user', 'role'),
        }),
        ('Metadatos', {
            'fields': ('assigned_at', 'assigned_by'),
            'classes': ('collapse',),
        }),
    )


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """
    Admin for RolePermission relationship.
    
    Features:
    - Display role and permission assignment
    - Filter by role and permission
    - Show assignment metadata
    """
    
    list_display = ('role', 'permission', 'granted_at', 'granted_by')
    list_filter = ('role', 'granted_at')
    search_fields = ('role__name', 'permission__code')
    readonly_fields = ('id', 'granted_at', 'granted_by')
    
    fieldsets = (
        ('Asignación', {
            'fields': ('id', 'role', 'permission'),
        }),
        ('Metadatos', {
            'fields': ('granted_at', 'granted_by'),
            'classes': ('collapse',),
        }),
    )


# Customize admin site
admin.site.site_header = 'Administración'
admin.site.site_title = 'Admin Aura Auth'
admin.site.index_title = 'Panel de Administración'

# Unregister Group from Django auth
admin.site.unregister(Group)

# Re-register Group under accounts app to appear in "Gestión de Usuarios"
@admin.register(GroupProxy)
class GroupAdmin(admin.ModelAdmin):
    """
    Custom admin for Group model to manage authentication groups.
    
    Appears under "Gestión de Usuarios" instead of "Autenticación y Autorización"
    """
    list_display = ('name', 'permission_count')
    search_fields = ('name',)
    filter_horizontal = ('permissions',)
    
    def permission_count(self, obj):
        """Display count of assigned permissions."""
        count = obj.permissions.count()
        return format_html(
            '<span style="background-color: #417690; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            count
        )
    permission_count.short_description = 'Permisos'


def _custom_get_app_list(self, request):
    """
    Custom ordering for models in the admin index.
    """
    app_list = admin.AdminSite.get_app_list(self, request)
    desired_order = [
        'User',
        'GroupProxy',
        'Role',
        'UserRole',
        'Permission',
        'RolePermission',
    ]
    order_map = {name: index for index, name in enumerate(desired_order)}

    for app in app_list:
        if app.get('app_label') == 'accounts':
            app['models'].sort(
                key=lambda model: order_map.get(model.get('object_name'), len(order_map))
            )
    return app_list


admin.site.get_app_list = _custom_get_app_list.__get__(admin.site, admin.AdminSite)
