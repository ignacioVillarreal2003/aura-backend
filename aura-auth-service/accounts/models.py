"""
User, Role, Permission models aligned with auth_db schema.

This module maps Django models to the PostgreSQL auth_db tables defined
in docker/auth-db/init.sql and keeps custom group and refresh token tables.
"""

import uuid
from django.apps import apps
from django.db import models, connection, transaction
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password


class AuditedModel(models.Model):
    """
    Abstract base model for custom tables that keep audit fields.
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
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class UserStatus(models.TextChoices):
    ACTIVE = 'active', 'Activo'
    INACTIVE = 'inactive', 'Inactivo'


class CustomUserManager(BaseUserManager):
    """
    Manager for custom User model aligned to auth_db schema.
    """

    def _bootstrap_create_user(self, username, email, password=None, **extra_fields):
        now = timezone.now()
        table = self.model._meta.db_table
        seq_expr = f"pg_get_serial_sequence('{table}', 'id')"
        status = extra_fields.get('status', UserStatus.ACTIVE)
        password_hash = make_password(password)
        with transaction.atomic(using=self._db):
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {table} (
                        id,
                        username,
                        email,
                        password,
                        status,
                        last_login,
                        account_non_expired,
                        account_non_locked,
                        failed_login_attempts,
                        lockout_until,
                        credentials_non_expired,
                        last_password_change,
                        enabled,
                        refresh_token,
                        created_by,
                        created_at,
                        updated_by,
                        updated_at,
                        deleted_by,
                        deleted_at
                    ) VALUES (
                        nextval({seq_expr}),
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        currval({seq_expr}),
                        %s, %s, %s, %s, %s
                    )
                    RETURNING id
                    """,
                    [
                        username,
                        email,
                        password_hash,
                        status,
                        extra_fields.get('last_login'),
                        extra_fields.get('account_non_expired', True),
                        extra_fields.get('account_non_locked', True),
                        extra_fields.get('failed_login_attempts'),
                        extra_fields.get('lockout_until'),
                        extra_fields.get('credentials_non_expired', True),
                        extra_fields.get('last_password_change', now),
                        extra_fields.get('is_active', True),
                        extra_fields.get('refresh_token'),
                        now,
                        extra_fields.get('updated_by_id'),
                        now,
                        extra_fields.get('deleted_by_id'),
                        extra_fields.get('deleted_at'),
                    ],
                )
                user_id = cursor.fetchone()[0]
        return self.get(pk=user_id)

    def create_user(self, username, email, password=None, created_by=None, **extra_fields):
        if not username:
            raise ValueError('Username is required')
        if not email:
            raise ValueError('Email is required')

        email = self.normalize_email(email)
        extra_fields.setdefault('status', UserStatus.ACTIVE)
        extra_fields.setdefault('account_non_expired', True)
        extra_fields.setdefault('account_non_locked', True)
        extra_fields.setdefault('credentials_non_expired', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('failed_login_attempts', 0)
        extra_fields.setdefault('last_password_change', timezone.now())

        if created_by is None:
            if self.model.objects.exists():
                raise ValueError('created_by is required when users already exist')
            return self._bootstrap_create_user(username, email, password, **extra_fields)

        user = self.model(username=username, email=email, **extra_fields)
        if isinstance(created_by, self.model):
            user.created_by = created_by
        else:
            user.created_by_id = created_by
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, created_by=None, **extra_fields):
        extra_fields.setdefault('status', UserStatus.ACTIVE)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('account_non_expired', True)
        extra_fields.setdefault('account_non_locked', True)
        extra_fields.setdefault('credentials_non_expired', True)

        user = self.create_user(username, email, password, created_by=created_by, **extra_fields)
        role_model = apps.get_model('accounts', 'Role')
        user_role_model = apps.get_model('accounts', 'UserRole')
        role, _ = role_model.objects.get_or_create(
            name='SUPER_ADMIN',
            defaults={'description': 'Super admin role'},
        )
        user_role_model.objects.get_or_create(
            user=user,
            role=role,
            defaults={'created_by': user},
        )
        return user


class User(AbstractBaseUser):
    """
    Custom User model aligned with auth_user table.
    """

    id = models.AutoField(primary_key=True)
    username = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Usuario',
        help_text="Unique username for login",
    )
    email = models.EmailField(
        max_length=255,
        unique=True,
        verbose_name='Correo',
        help_text="Unique email address",
    )
    password = models.CharField(
        max_length=255,
        verbose_name='Contraseña',
        help_text="Hashed password",
    )
    status = models.CharField(
        max_length=8,
        choices=UserStatus.choices,
        verbose_name='Estado',
    )
    last_login = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Último login',
    )
    account_non_expired = models.BooleanField(default=True)
    account_non_locked = models.BooleanField(default=True)
    failed_login_attempts = models.IntegerField(null=True, blank=True)
    lockout_until = models.DateTimeField(null=True, blank=True)
    credentials_non_expired = models.BooleanField(default=True)
    last_password_change = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(
        default=True,
        db_column='enabled',
        verbose_name='Habilitado',
    )
    refresh_token = models.UUIDField(null=True, blank=True)
    created_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='created_users',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='updated_users',
        db_column='updated_by',
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    deleted_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='deleted_users',
        db_column='deleted_by',
        null=True,
        blank=True,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    custom_groups = models.ManyToManyField(
        'CustomGroup',
        blank=True,
        related_name='users',
        verbose_name='Grupos',
    )

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'auth_user'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.username} ({self.email})"

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.last_password_change = timezone.now()

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def delete(self, using=None, keep_parents=False, deleted_by=None):
        self.soft_delete(deleted_by=deleted_by)
        return None

    @property
    def is_staff(self) -> bool:
        if not self.pk:
            return False
        return self.user_roles.filter(
            role__name__in=['SUPER_ADMIN', 'ADMIN'],
            deleted_at__isnull=True,
        ).exists()

    @property
    def is_superuser(self) -> bool:
        if not self.pk:
            return False
        return self.user_roles.filter(role__name='SUPER_ADMIN', deleted_at__isnull=True).exists()

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser

    def soft_delete(self, deleted_by=None):
        self.deleted_at = timezone.now()
        if deleted_by is not None:
            if isinstance(deleted_by, User):
                self.deleted_by = deleted_by
            else:
                self.deleted_by_id = deleted_by
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['deleted_at', 'deleted_by', 'updated_at'])

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class CustomGroup(AuditedModel):
    """
    Custom group model detached from permissions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        verbose_name='Nombre'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    documents = models.ManyToManyField(
        'documents.Document',
        blank=True,
        related_name='groups',
        verbose_name='Documentos'
    )

    class Meta:
        db_table = 'custom_groups'
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
        indexes = [
            models.Index(fields=['name'], name='custom_gro_name_8c5f90_idx'),
            models.Index(fields=['deleted_at'], name='custom_gro_deleted_2b06a5_idx'),
        ]

    def __str__(self):
        return self.name


class Role(models.Model):
    """
    Role model aligned with role table.
    """

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
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.name


class Permission(models.Model):
    """
    Permission model aligned with permission table.
    """

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
    """
    User-role relationship aligned with auth_user_in_role table.
    """

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
    """
    Role-permission relationship aligned with permission_in_role table.
    """

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


class RefreshToken(AuditedModel):
    """
    Refresh token table for auth sessions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name='Token',
        help_text="Unique refresh token value (UUID)",
    )
    is_revoked = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Revocado',
        help_text="Whether this token has been revoked",
    )
    expires_at = models.DateTimeField(
        verbose_name='Expira el',
        help_text="Token expiration timestamp",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP',
        help_text="Client IP address when token was issued",
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent',
        help_text="Client User-Agent when token was issued",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='refresh_tokens',
        verbose_name='Usuario',
        help_text="User who owns this refresh token",
    )

    class Meta:
        db_table = 'refresh_tokens'
        verbose_name = 'Token de Refresco'
        verbose_name_plural = 'Tokens de Refresco'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['token']),
            models.Index(fields=['is_revoked']),
            models.Index(fields=['expires_at']),
        ]


