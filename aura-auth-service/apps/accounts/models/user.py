"""Modelo y manager de usuario, alineados al esquema de auth_db."""

from functools import cached_property

from django.apps import apps
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models, connection, transaction
from django.utils import timezone


class UserStatus(models.TextChoices):
    ACTIVE = 'active', 'Activo'
    INACTIVE = 'inactive', 'Inactivo'


class CustomUserManager(BaseUserManager):
    """Manager del modelo de usuario."""

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
                        enabled,
                        last_login,
                        account_non_expired,
                        account_non_locked,
                        failed_login_attempts,
                        lockout_until,
                        credentials_non_expired,
                        last_password_change,
                        created_by,
                        created_at,
                        updated_by,
                        updated_at,
                        deleted_by,
                        deleted_at
                    ) VALUES (
                        nextval({seq_expr}),
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
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
                        extra_fields.get('enabled', True),
                        extra_fields.get('last_login'),
                        extra_fields.get('account_non_expired', True),
                        extra_fields.get('account_non_locked', True),
                        extra_fields.get('failed_login_attempts'),
                        extra_fields.get('lockout_until'),
                        extra_fields.get('credentials_non_expired', True),
                        extra_fields.get('last_password_change', now),
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
        extra_fields.setdefault('failed_login_attempts', 0)
        extra_fields.setdefault('last_password_change', timezone.now())

        if created_by is None:
            if self.model.objects.exists():
                created_by = self.model.objects.order_by('id').first()
            else:
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
        extra_fields.setdefault('account_non_expired', True)
        extra_fields.setdefault('account_non_locked', True)
        extra_fields.setdefault('credentials_non_expired', True)

        user = self.create_user(username, email, password, created_by=created_by, **extra_fields)
        role_model = apps.get_model('accounts', 'Role')
        user_role_model = apps.get_model('accounts', 'UserRole')
        role, _ = role_model.objects.get_or_create(
            name='superadmin',
            defaults={'description': 'Super admin role'},
        )
        user_role_model.objects.get_or_create(
            user=user,
            role=role,
            defaults={'created_by': user},
        )
        return user


class User(AbstractBaseUser):
    """Modelo de usuario (tabla auth_user)."""

    id = models.AutoField(primary_key=True)
    username = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Usuario',
    )
    name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name='Nombre',
    )
    email = models.EmailField(
        max_length=255,
        unique=True,
        verbose_name='Correo',
    )
    password = models.CharField(
        max_length=255,
        verbose_name='Contraseña',
        help_text="Hashed password",
    )
    enabled = models.BooleanField(default=True)
    status = models.CharField(
        max_length=8,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
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
    last_password_change = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Ultimo cambio de contrasena',
    )
    refresh_token = models.UUIDField(null=True, blank=True)
    force_logout_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Forzar cierre de sesión desde',
        help_text='Tokens emitidos antes de este momento son rechazados inmediatamente.',
    )
    created_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='created_users',
        db_column='created_by',
        verbose_name='Creado por',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha creado')
    updated_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='updated_users',
        db_column='updated_by',
        null=True,
        blank=True,
        verbose_name='Actualizado por',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha actualizado')
    deleted_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='deleted_users',
        db_column='deleted_by',
        null=True,
        blank=True,
        verbose_name='Eliminado por',
    )
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Fecha eliminado')
    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'auth_user'
        managed = False
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

    # ``cached_property``: estas propiedades golpeaban la BD en cada acceso y se
    # leen muchas veces por request (permisos de DRF/admin). El cache es por
    # instancia, asi que vive solo durante el request actual del usuario.
    @cached_property
    def is_staff(self) -> bool:
        if not self.pk:
            return False
        return self.user_roles.filter(
            role__name__in=['superadmin', 'admin'],
            deleted_at__isnull=True,
        ).exists()

    @cached_property
    def is_superuser(self) -> bool:
        if not self.pk:
            return False
        return self.user_roles.filter(role__name='superadmin', deleted_at__isnull=True).exists()

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
