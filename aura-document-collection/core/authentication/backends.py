from rest_framework.authentication import BaseAuthentication


class ServiceAuthentication(BaseAuthentication):
    """Reads AuthenticatedUser set by AuthenticationMiddleware on the request."""

    def authenticate(self, request):
        user = getattr(request, "authenticated_user", None)
        if user is None:
            return None
        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"
