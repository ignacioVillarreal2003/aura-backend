"""Middleware that attaches elevation context to every request."""

from accounts.services.elevation_service import is_elevated, get_real_user


class ElevationMiddleware:
    """
    Attaches elevation context to every request.
    Sets request.is_elevated and request.real_user so views and admin can access them easily.
    Auto-drops the session if the elevation window has expired.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            request.is_elevated = is_elevated(request)
            request.real_user = get_real_user(request)
        else:
            request.is_elevated = False
            request.real_user = None

        return self.get_response(request)
