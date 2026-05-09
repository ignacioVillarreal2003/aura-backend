"""Audit helpers for accounts admin."""

import logging

from accounts.models import User

logger = logging.getLogger(__name__)


def log_audit(actor, action: str, entity_type: str,
              entity_id=None, entity_label: str = None,
              details: dict = None, source: str = 'admin') -> None:
    """
    Append one row to audit_log.

    :param actor:        User instance or None (system action).
    :param action:       Verb in uppercase: CREATE, UPDATE, DELETE, LOGIN, LOGOUT, etc.
    :param entity_type:  Logical name of the affected model (e.g. 'auth_user', 'role').
    :param entity_id:    PK of the affected record (will be coerced to str).
    :param entity_label: Human-readable identifier cached at write time (e.g. username).
    :param details:      Optional dict with extra context (changed fields, old values, …).
    :param source:       'admin' | 'api' — where the action originated.
    """
    try:
        from accounts.models import AuditLog
    except ImportError:
        logger.debug(
            'log_audit skipped: AuditLog model is not exposed on accounts.models'
        )
        return
    try:
        AuditLog.objects.create(
            actor_id=getattr(actor, 'pk', None) if actor else None,
            actor_username=getattr(actor, 'username', str(actor)) if actor else None,
            action=action.upper(),
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            entity_label=entity_label,
            details=details,
            source=source,
        )
    except Exception as exc:
        # Audit failures must NEVER break the main operation.
        logger.error('log_audit failed: %s', exc, exc_info=True)


def _apply_audit_fields(obj, actor, is_create: bool):
    if is_create:
        if hasattr(obj, 'created_by_id'):
            # FK field (e.g. User.created_by → User): assign the object itself
            if not obj.created_by_id:
                obj.created_by = actor
        else:
            # BigInt field: store the user's pk
            if not obj.created_by:
                obj.created_by = getattr(actor, 'pk', actor)

    if hasattr(obj, 'updated_by_id'):
        # FK field
        obj.updated_by = actor
    else:
        # BigInt field
        obj.updated_by = getattr(actor, 'pk', actor)


def _is_super_admin_user(user: User) -> bool:
    return bool(user and user.is_superuser)


def _has_role(user: User, role_name: str) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if not hasattr(user, 'user_roles'):
        return False
    return user.user_roles.filter(
        role__name=role_name,
        deleted_at__isnull=True,
    ).exists()


def _is_admin_user(user: User) -> bool:
    return _has_role(user, 'admin') and not _is_super_admin_user(user)


def _is_admin_or_super_user(user: User) -> bool:
    return _is_super_admin_user(user) or _is_admin_user(user)
