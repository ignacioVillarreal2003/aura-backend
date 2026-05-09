from rest_framework.authentication import BaseAuthentication


class ServiceAuthentication(BaseAuthentication):
    """DRF authentication adapter that surfaces the user attached by
    `AuthenticationMiddleware` onto `request.user` so DRF permission classes
    such as `IsAuthenticated` work as expected."""

    def authenticate(self, request):
        user = getattr(request, "authenticated_user", None)
        if user is None:
            return None
        return (user, None)

    def authenticate_header(self, request):
        return "Bearer"
