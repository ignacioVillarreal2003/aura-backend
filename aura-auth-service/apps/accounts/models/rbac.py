"""Modelos de roles, permisos y sus relaciones."""

from django.db import models
from apps.accounts.models.user import User


class Role(models.Model):
    """Modelo de rol (tabla role)."""

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
        managed = False
        verbose_name = 'Rol de sistema'
        verbose_name_plural = 'Roles de sistema'

    def __str__(self):
        return self.name


class Permission(models.Model):
    """Modelo de permiso (tabla permission)."""

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
        managed = False
        verbose_name = 'Permiso'
        verbose_name_plural = 'Permisos'

    def __str__(self):
        return self.name


class UserRole(models.Model):
    """Relacion usuario-rol (tabla auth_user_in_role)."""

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        related_name='user_roles',
        db_column='auth_user_id',
        verbose_name='Usuario',
        help_text="User reference",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.DO_NOTHING,
        related_name='user_assignments',
        db_column='role_id',
        verbose_name='Rol',
        help_text="Role reference",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        related_name='created_user_roles',
        db_column='created_by',
    )
    created_at = models.DateField(auto_now_add=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        related_name='deleted_user_roles',
        db_column='deleted_by',
        null=True,
        blank=True,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'auth_user_in_role'
        managed = False
        verbose_name = 'Rol de Usuario'
        verbose_name_plural = 'Roles de Usuario'

    def __str__(self):
        return f"{self.user.username} -> {self.role.name}"


class PermissionInRole(models.Model):
    """Relacion rol-permiso (tabla permission_in_role)."""

    id = models.AutoField(primary_key=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='permission_links',
        db_column='role_id',
        verbose_name='Rol',
        help_text="Role reference",
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='role_links',
        db_column='permission_id',
        verbose_name='Permiso',
        help_text="Permission reference",
    )

    class Meta:
        db_table = 'permission_in_role'
        managed = False
        verbose_name = 'Permiso de Rol'
        verbose_name_plural = 'Permisos de Rol'

    def __str__(self):
        return f"{self.role.name} -> {self.permission.name}"


