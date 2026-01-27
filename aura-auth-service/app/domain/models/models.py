from django.db import models
from django.contrib.auth.hashers import make_password
import uuid


class UserStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'


class AuthUser(models.Model):
    """
    Model that maps the existing auth_user table in the database.
    Represents a user in the authentication system.
    """
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    password = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE
    )
    last_login = models.DateTimeField(null=True, blank=True)
    account_non_expired = models.BooleanField(default=True)
    account_non_locked = models.BooleanField(default=True)
    failed_login_attempts = models.IntegerField(default=0, null=True, blank=True)
    lockout_until = models.DateTimeField(null=True, blank=True)
    credentials_non_expired = models.BooleanField(default=True)
    last_password_change = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    refresh_token = models.UUIDField(null=True, blank=True)
    
    # Audit fields
    created_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='created_users',
        null=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='updated_users',
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    deleted_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='deleted_users',
        null=True,
        blank=True
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'auth_user'
        managed = False
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.email})"

    def set_password(self, raw_password):
        """Hash and assign the password."""
        self.password = make_password(raw_password)


class Role(models.Model):
    """
    Model that maps the existing role table in the database.
    Represents a role in the system.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=255)

    class Meta:
        db_table = 'role'
        managed = False
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.name


class AuthUserInRole(models.Model):
    """
    Model that maps the existing auth_user_in_role table.
    Represents the M2M relationship between users and roles.
    """
    id = models.AutoField(primary_key=True)
    auth_user = models.ForeignKey(
        AuthUser,
        on_delete=models.CASCADE,
        db_column='auth_user_id',
        related_name='user_roles'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        db_column='role_id',
        related_name='role_users'
    )
    created_by = models.ForeignKey(
        AuthUser,
        on_delete=models.PROTECT,
        related_name='assigned_roles',
        db_column='created_by_id'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.ForeignKey(
        AuthUser,
        on_delete=models.SET_NULL,
        related_name='unassigned_roles',
        null=True,
        blank=True,
        db_column='deleted_by_id'
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'auth_user_in_role'
        managed = False
        verbose_name = 'User In Role'
        verbose_name_plural = 'Users In Roles'
        unique_together = ('auth_user', 'role')

    def __str__(self):
        return f"{self.auth_user.username} - {self.role.name}"


class Permission(models.Model):
    """
    Model that maps the existing permission table in the database.
    Represents a permission in the system.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'permission'
        managed = False
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'

    def __str__(self):
        return self.name


class PermissionInRole(models.Model):
    """
    Model that maps the existing permission_in_role table.
    Represents the M2M relationship between permissions and roles.
    """
    id = models.AutoField(primary_key=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        db_column='role_id',
        related_name='role_permissions'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        db_column='permission_id',
        related_name='permission_roles'
    )

    class Meta:
        db_table = 'permission_in_role'
        managed = False
        verbose_name = 'Permission In Role'
        verbose_name_plural = 'Permissions In Roles'
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role.name} - {self.permission.name}"
