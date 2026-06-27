"""Middleware que agrega el contexto de elevacion a cada peticion."""

from apps.accounts.services.elevation_service import is_elevated, get_real_user


class ElevationMiddleware:
    """Deja request.is_elevated y request.real_user disponibles en cada peticion."""

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
