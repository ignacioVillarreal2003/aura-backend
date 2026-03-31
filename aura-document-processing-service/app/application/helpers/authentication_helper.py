from app.domain.authentication.authenticated_user import AuthenticatedUser


def has_any_role(authenticated_user: AuthenticatedUser, roles: set[str]) -> bool:
    return bool(set(authenticated_user.roles) & roles)