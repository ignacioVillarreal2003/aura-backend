from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.authentication.authenticated_user import AuthenticatedUser


class ServiceAuthentication(BaseAuthentication):
    """
    DRF authentication backend that reads the AuthenticatedUser
    set by the AuthenticationMiddleware on the request object.
    """

    def authenticate(self, request):
        user: AuthenticatedUser | None = getattr(request, "authenticated_user", None)
        if user is None:
            return None
        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"
