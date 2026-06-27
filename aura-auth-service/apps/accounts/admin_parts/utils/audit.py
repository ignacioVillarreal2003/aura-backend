"""Helpers de auditoria para el admin de accounts."""

import logging

from apps.accounts.models import User

logger = logging.getLogger(__name__)


def log_audit(actor, action: str, entity_type: str,
              entity_id=None, entity_label: str = None,
              details: dict = None, source: str = 'admin',
              request=None) -> None:
    """Agrega una fila al registro de auditoria (audit_log)."""
    if source == 'admin':
        if request is not None and _is_effective_superadmin(request):
            source = 'superadmin'
        elif actor is not None and _is_super_admin_user(actor):
            source = 'superadmin'
    try:
        from apps.accounts.models import AuditLog
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
        logger.error('log_audit failed: %s', exc, exc_info=True)


def _apply_audit_fields(obj, actor, is_create: bool):
    if is_create:
        if hasattr(obj, 'created_by_id'):
            if not obj.created_by_id:
                obj.created_by = actor
        else:
            if not obj.created_by:
                obj.created_by = getattr(actor, 'pk', actor)

    if hasattr(obj, 'updated_by_id'):
        obj.updated_by = actor
    else:
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


def _is_effective_superadmin(request) -> bool:
    """True para superadmins reales y para admins en modo elevado."""
    user = getattr(request, 'user', None)
    if _is_super_admin_user(user):
        return True
    return _is_admin_user(user) and getattr(request, 'is_elevated', False)
