"""RBAC models for roles, permissions, and relationships."""

from django.db import models
from accounts.models.user import User


class Role(models.Model):
    """Role model aligned with role table."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=255,
        verbose_name='Nombre',
    )
    description = models.CharField(
        max_length=255,
        verbose_name='Descripción',
    )

    class Meta:
        db_table = 'role'
        verbose_name = 'Rol de sistema'
        verbose_name_plural = 'Roles de sistema'

    def __str__(self):
        return self.name


class Permission(models.Model):
    """Permission model aligned with permission table."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=255,
        verbose_name='Nombre',
    )
    description = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Descripción',
    )

    class Meta:
        db_table = 'permission'
        verbose_name = 'Permiso'
        verbose_name_plural = 'Permisos'

    def __str__(self):
        return self.name


class UserRole(models.Model):
    """User-role relationship aligned with auth_user_in_role table."""

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='user_roles',
        db_column='auth_user_id',
        verbose_name='Usuario',
        help_text="User reference",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='user_assignments',
        db_column='role_id',
        verbose_name='Rol',
        help_text="Role reference",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_user_roles',
        db_column='created_by',
    )
    created_at = models.DateField(auto_now_add=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='deleted_user_roles',
        db_column='deleted_by',
        null=True,
        blank=True,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'auth_user_in_role'
        verbose_name = 'Rol de Usuario'
        verbose_name_plural = 'Roles de Usuario'

    def __str__(self):
        return f"{self.user.username} -> {self.role.name}"


class PermissionInRole(models.Model):
    """Role-permission relationship aligned with permission_in_role table."""

    id = models.AutoField(primary_key=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='permission_links',
        db_column='role_id',
        verbose_name='Rol',
        help_text="Role reference",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.PROTECT,
        related_name='role_links',
        db_column='permission_id',
        verbose_name='Permiso',
        help_text="Permission reference",
    )

    class Meta:
        db_table = 'permission_in_role'
        verbose_name = 'Permiso de Rol'
        verbose_name_plural = 'Permisos de Rol'

    def __str__(self):
        return f"{self.role.name} -> {self.permission.name}"


class FauRole(models.Model):
    """FAU role catalog (e.g., General, Capitán, Cabo)."""

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, verbose_name='Nombre')
    description = models.CharField(max_length=255, blank=True, verbose_name='Descripción')

    class Meta:
        db_table = 'fau_role'
        verbose_name = 'Rol FAU'
        verbose_name_plural = 'Rol FAU'

    def __str__(self):
        return self.name
