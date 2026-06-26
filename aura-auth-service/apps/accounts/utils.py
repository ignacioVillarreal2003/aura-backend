"""
Utility functions for RBAC operations.

This module provides helper functions for common RBAC operations
like checking permissions, assigning roles, etc.
"""

from apps.accounts.models import User, Permission


def _normalize_permission_name(permission_name: str) -> str:
    """Normalize permission names to UPPER_SNAKE_CASE."""
    return (permission_name or '').strip().replace('.', '_').upper()


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
