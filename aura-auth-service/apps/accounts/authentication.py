"""Backends de autenticacion de DRF para la API.

JWTAuthentication resuelve un User real; ServiceKeyAuthentication resuelve un
ServiceAccount para llamadas de confianza entre servicios.
"""

import logging
import secrets

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.services.auth_service import authenticate_access_token

logger = logging.getLogger(__name__)


class ServiceAccount:
    """Identidad minima para peticiones entre servicios (no es un usuario real)."""

    is_authenticated = True
    is_active = True
    is_service = True
    is_superuser = False
    id = 0
    pk = 0
    username = "service"

    def __str__(self):
        return "service"


class JWTAuthentication(BaseAuthentication):
    """Autenticacion por bearer token. Devuelve None si no hay header Bearer."""

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return None

        user = authenticate_access_token(token)
        if not user:
            logger.warning(
                "JWT authentication failed: invalid or expired token.",
                extra={"path": request.path},
            )
            raise AuthenticationFailed("Invalid or expired token.")

        return (user, token)

    def authenticate_header(self, request):
        return "Bearer"


class ServiceKeyAuthentication(BaseAuthentication):
    """Autenticacion entre servicios con el header X-Service-Api-Key."""

    def authenticate(self, request):
        api_key = request.headers.get("X-Service-Api-Key")
        if not api_key:
            return None

        expected = getattr(settings, "SERVICE_API_KEY", "")
        if not expected:
            logger.error("SERVICE_API_KEY is not configured.")
            raise AuthenticationFailed("Service authentication not configured.")

        if not secrets.compare_digest(api_key.strip(), str(expected)):
            logger.warning("Service API key rejected.", extra={"path": request.path})
            raise AuthenticationFailed("Invalid service API key.")

        return (ServiceAccount(), api_key)

    def authenticate_header(self, request):
        return "X-Service-Api-Key"
