from django.utils import timezone
from accounts.models import Role, UserRole


def assign_roles_to_user(user, selected_role, actor, protect_system_roles: bool = True) -> None:
    """
    Set the user's active role assignment to selected_role.

    When protect_system_roles is True, existing superadmin/admin assignments are
    preserved even if not selected — non-super-admins cannot strip those roles.
    """
    selected_roles = [selected_role] if selected_role else []

    if protect_system_roles:
        protected = Role.objects.filter(
            name__in=['superadmin', 'admin'],
            user_assignments__user=user,
            user_assignments__deleted_at__isnull=True,
        )
        for role in protected:
            if role not in selected_roles:
                selected_roles.append(role)

    UserRole.objects.filter(
        user=user,
        deleted_at__isnull=True,
    ).exclude(role__in=selected_roles).update(
        deleted_at=timezone.now(),
        deleted_by=actor,
    )

    existing_role_ids = set(
        UserRole.objects.filter(user=user, deleted_at__isnull=True)
        .values_list('role_id', flat=True)
    )
    to_create = [
        UserRole(user=user, role=role, created_by=actor)
        for role in selected_roles
        if role.id not in existing_role_ids
    ]
    if to_create:
        UserRole.objects.bulk_create(to_create)
