"""
Utility functions for RBAC operations.

This module provides helper functions for common RBAC operations
like checking permissions, assigning roles, etc.
"""

from accounts.models import User, Role, Permission, UserRole, PermissionInRole


def _normalize_permission_name(permission_name: str) -> str:
    """Normalize permission names to UPPER_SNAKE_CASE."""
    return (permission_name or '').strip().replace('.', '_').upper()


def assign_role_to_user(user: User, role: Role, created_by: User) -> UserRole:
    """
    Assign a role to a user.
    
    Args:
        user: User instance
        role: Role instance
        created_by: User who assigned the role

    Returns:
        UserRole instance
    """
    user_role = UserRole.objects.filter(
        user=user,
        role=role,
        deleted_at__isnull=True,
    ).first()
    if user_role:
        return user_role

    user_role = UserRole.objects.filter(
        user=user,
        role=role,
        deleted_at__isnull=False,
    ).first()
    if user_role:
        user_role.deleted_at = None
        user_role.deleted_by = None
        user_role.created_by = created_by
        user_role.save(update_fields=['deleted_at', 'deleted_by', 'created_by'])
        return user_role

    return UserRole.objects.create(
        user=user,
        role=role,
        created_by=created_by,
    )


def assign_permission_to_role(role: Role, permission: Permission) -> PermissionInRole:
    """
    Assign a permission to a role.
    
    Args:
        role: Role instance
        permission: Permission instance

    Returns:
        PermissionInRole instance
    """
    role_perm, _ = PermissionInRole.objects.get_or_create(
        role=role,
        permission=permission,
    )
    return role_perm


def user_has_permission(user: User, permission_name: str) -> bool:
    """
    Check if a user has a specific permission.
    
    Args:
        user: User instance
        permission_name: Permission name (e.g., "user.create")

    Returns:
        True if user has permission, False otherwise
    """
    normalized_permission = _normalize_permission_name(permission_name)
    if user.is_superuser:
        return True
    return normalized_permission in get_user_permissions(user)


def user_has_role(user: User, role_name: str) -> bool:
    """
    Check if a user has a specific role.
    
    Args:
        user: User instance
        role_name: Role name (e.g., "superadmin")
        
    Returns:
        True if user has role, False otherwise
    """
    normalized_role = (role_name or '').lower()
    return user.user_roles.filter(
        role__name=normalized_role,
        deleted_at__isnull=True,
    ).exists() or user.is_superuser


def get_user_permissions(user: User) -> list:
    """
    Get all permissions for a user.
    
    Args:
        user: User instance
        
    Returns:
        List of permission names
    """
    if user.is_superuser:
        permissions = [
            _normalize_permission_name(name)
            for name in Permission.objects.values_list('name', flat=True)
            if name
        ]
        return list(set(permissions))

    permissions = [
        _normalize_permission_name(name) for name in
        user.user_roles.filter(deleted_at__isnull=True).values_list(
            'role__permission_links__permission__name',
            flat=True,
        )
        if name
    ]
    return list(set(permissions))


def get_user_roles(user: User) -> list:
    """
    Get all roles for a user.
    
    Args:
        user: User instance
        
    Returns:
        List of role names
    """
    roles = [
        name.lower() for name in
        user.user_roles.filter(deleted_at__isnull=True).values_list('role__name', flat=True)
        if name
    ]
    return list(set(roles))
