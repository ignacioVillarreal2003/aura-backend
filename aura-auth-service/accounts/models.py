"""
User, Role, Permission models and their relationships.

This module implements the core RBAC (Role-Based Access Control) system
with soft delete support and audit fields on all models.

Models:
- AuditedModel: Abstract base model with audit fields (created_at, created_by, etc.)
- User: Custom user model with soft delete
- Role: Role definition with permissions
- Permission: Permission definition
- UserRole: User-Role relationship
- RolePermission: Role-Permission relationship
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group
from django.utils import timezone
from django.contrib.auth.hashers import make_password


class AuditedModel(models.Model):
    """
    Abstract base model for all entities.
    
    Provides audit fields:
    - created_at: Timestamp when created
    - created_by: User who created the record
    - updated_at: Timestamp of last update
    - updated_by: User who last updated the record
    - deleted_at: Soft delete timestamp (null = active)
    - deleted_by: User who deleted the record
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado',
        help_text="Creation timestamp"
    )
    created_by = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Creado por',
        help_text="Username who created this record"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado el',
        help_text="Last update timestamp"
    )
    updated_by = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Actualizado por',
        help_text="Username who last updated this record"
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Eliminado el',
        help_text="Soft delete timestamp (null = active)"
    )
    deleted_by = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Eliminado por',
        help_text="Username who deleted this record"
    )

    class Meta:
        abstract = True

    def soft_delete(self, deleted_by: str = None):
        """
        Soft delete this record.
        
        Args:
            deleted_by: Username performing the deletion
        """
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    def restore(self):
        """
        Restore a soft-deleted record.
        """
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    @property
    def is_deleted(self) -> bool:
        """Check if this record is soft-deleted."""
        return self.deleted_at is not None


class CustomUserManager(BaseUserManager):
    """
    Manager for custom User model.
    """

    def create_user(self, username, email, password=None, **extra_fields):
        """
        Create and save a regular user.
        """
        if not username:
            raise ValueError('Username is required')
        if not email:
            raise ValueError('Email is required')

        email = self.normalize_email(email)
        extra_fields.setdefault('is_super_admin', False)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        """
        Create and save a superuser.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_super_admin', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, AuditedModel):
    """
    Custom User model for the authentication service.
    
    Fields:
    - id: UUID primary key
    - username: Unique username
    - email: Unique email address
    - password_hash: Hashed password
    - is_active: Whether user can login
    - Audit fields from AuditedModel
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        verbose_name='Usuario',
        help_text="Unique username for login"
    )
    email = models.EmailField(
        unique=True,
        db_index=True,
        verbose_name='Correo',
        help_text="Unique email address"
    )
    password = models.CharField(
        max_length=255,
        verbose_name='Contraseña',
        help_text="Hashed password"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text="Whether this user can login"
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name='Es staff',
        help_text="Whether user can access admin panel"
    )
    is_superuser = models.BooleanField(
        default=False,
        verbose_name='Es superusuario',
        help_text="Whether user has all permissions"
    )
    is_super_admin = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Es Super Admin',
        help_text="Super admin bypass all permission checks"
    )
    last_login = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Último login'
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'users'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
            models.Index(fields=['deleted_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['username'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_username'
            ),
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_email'
            ),
        ]

    def __str__(self):
        return f"{self.username} ({self.email})"

    def set_password(self, raw_password):
        """Hash and set the password."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Check if the provided password matches the hash."""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    def delete(self, using=None, keep_parents=False, deleted_by=None):
        """Soft delete user records by default."""
        self.soft_delete(deleted_by=deleted_by)
        return None


class Role(AuditedModel):
    """
    Role model for RBAC.
    
    Represents a role that can be assigned to users.
    A role contains multiple permissions.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name='Nombre',
        help_text="Unique role name (e.g., SUPER_ADMIN, USER)"
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text="Role description and purpose"
    )

    class Meta:
        db_table = 'roles'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['deleted_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_role_name'
            ),
        ]

    def __str__(self):
        return self.name


class Permission(AuditedModel):
    """
    Permission model for RBAC.
    
    Represents a specific permission that can be granted to roles.
    Permissions are fine-grained actions (e.g., 'user.create', 'role.edit').
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name='Código',
        help_text="Unique permission code (e.g., 'user.create', 'role.delete')"
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descripción',
        help_text="Permission description"
    )

    class Meta:
        db_table = 'permissions'
        verbose_name = 'Permiso'
        verbose_name_plural = 'Permisos'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['deleted_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['code'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_active_permission_code'
            ),
        ]

    def __str__(self):
        return self.code


class UserRole(models.Model):
    """
    UserRole relationship model.
    
    Represents the many-to-many relationship between User and Role.
    A user can have multiple roles, and a role can be assigned to multiple users.
    
    This model uses explicit through table for better auditability.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_roles',
        verbose_name='Usuario',
        help_text="User reference"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_assignments',
        verbose_name='Rol',
        help_text="Role reference"
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Asignado el',
        help_text="When this role was assigned"
    )
    assigned_by = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Asignado por',
        help_text="Username who assigned this role"
    )

    class Meta:
        db_table = 'user_roles'
        verbose_name = 'Rol de Usuario'
        verbose_name_plural = 'Roles de Usuario'
        unique_together = [('user', 'role')]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.role.name}"


class RolePermission(models.Model):
    """
    RolePermission relationship model.
    
    Represents the many-to-many relationship between Role and Permission.
    A role can have multiple permissions, and a permission can belong to multiple roles.
    
    This model uses explicit through table for better auditability.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_permissions',
        verbose_name='Rol',
        help_text="Role reference"
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='permission_roles',
        verbose_name='Permiso',
        help_text="Permission reference"
    )
    granted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Concedido el',
        help_text="When this permission was granted"
    )
    granted_by = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Concedido por',
        help_text="Username who granted this permission"
    )

    class Meta:
        db_table = 'role_permissions'
        verbose_name = 'Permiso de Rol'
        verbose_name_plural = 'Permisos de Rol'
        unique_together = [('role', 'permission')]
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['permission']),
        ]

    def __str__(self):
        return f"{self.role.name} -> {self.permission.code}"


class GroupProxy(Group):
    """
    Proxy model to show Django auth groups under the accounts app.
    """

    class Meta:
        proxy = True
        app_label = 'accounts'
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
