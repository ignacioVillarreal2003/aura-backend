"""
Utility functions for RBAC operations.

This module provides helper functions for common RBAC operations
like checking permissions, assigning roles, etc.
"""

from accounts.models import User, Role, Permission, UserRole, RolePermission


def assign_role_to_user(user: User, role: Role, assigned_by: str = None) -> UserRole:
    """
    Assign a role to a user.
    
    Args:
        user: User instance
        role: Role instance
        assigned_by: Username of who assigned the role
        
    Returns:
        UserRole instance
    """
    user_role, created = UserRole.objects.get_or_create(
        user=user,
        role=role,
        defaults={'assigned_by': assigned_by}
    )
    return user_role


def assign_permission_to_role(role: Role, permission: Permission, granted_by: str = None) -> RolePermission:
    """
    Assign a permission to a role.
    
    Args:
        role: Role instance
        permission: Permission instance
        granted_by: Username of who granted the permission
        
    Returns:
        RolePermission instance
    """
    role_perm, created = RolePermission.objects.get_or_create(
        role=role,
        permission=permission,
        defaults={'granted_by': granted_by}
    )
    return role_perm


def user_has_permission(user: User, permission_code: str) -> bool:
    """
    Check if a user has a specific permission.
    
    Args:
        user: User instance
        permission_code: Permission code (e.g., "user.create")
        
    Returns:
        True if user has permission, False otherwise
    """
    return user.user_roles.filter(
        role__role_permissions__permission__code=permission_code,
        role__deleted_at__isnull=True
    ).exists() or user.is_superuser


def user_has_role(user: User, role_name: str) -> bool:
    """
    Check if a user has a specific role.
    
    Args:
        user: User instance
        role_name: Role name (e.g., "SUPER_ADMIN")
        
    Returns:
        True if user has role, False otherwise
    """
    return user.user_roles.filter(
        role__name=role_name,
        role__deleted_at__isnull=True
    ).exists() or user.is_superuser


def get_user_permissions(user: User) -> list:
    """
    Get all permissions for a user.
    
    Args:
        user: User instance
        
    Returns:
        List of permission codes
    """
    if user.is_superuser:
        return list(Permission.objects.filter(deleted_at__isnull=True).values_list('code', flat=True))
    
    return list(
        user.user_roles.filter(
            role__deleted_at__isnull=True
        ).values_list(
            'role__role_permissions__permission__code',
            flat=True
        ).distinct()
    )


def get_user_roles(user: User) -> list:
    """
    Get all roles for a user.
    
    Args:
        user: User instance
        
    Returns:
        List of Role instances
    """
    return list(
        user.user_roles.filter(role__deleted_at__isnull=True).values_list('role', flat=True)
    )
