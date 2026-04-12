"""Audit helpers for accounts admin."""

from accounts.models import User


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
