import logging
from typing import Optional

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import JsonResponse

from core.authentication.authenticated_user import AuthenticatedUser
from core.authentication.exceptions import (
    AuthenticationProviderException,
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException,
)
from core.authentication.provider import authentication_provider

logger = logging.getLogger(__name__)

_WWW_AUTH = {"WWW-Authenticate": "Bearer"}


class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.excluded_paths: list[str] = getattr(
            settings, "AUTHENTICATION_EXCLUDED_PATHS", []
        )

    def __call__(self, request):
        if self._is_excluded(request.path):
            request.authenticated_user = None
            return self.get_response(request)

        service_user = authentication_provider.evaluate_service_auth(request)
        if service_user is not None:
            request.authenticated_user = service_user
            logger.debug(
                "Request authenticated with service credentials.",
                extra={"user_id": service_user.id, "path": request.path},
            )
            return self.get_response(request)

        token = self._extract_token(request)
        if not token:
            request.authenticated_user = None
            return self.get_response(request)

        return self._validate_jwt(request, token)

    def _validate_jwt(self, request, token: str):
        try:
            authenticated_user = async_to_sync(authentication_provider.validate_token)(token)
            request.authenticated_user = authenticated_user
            logger.debug(
                "Request authenticated with a valid bearer token.",
                extra={"user_id": authenticated_user.id, "path": request.path},
            )
            return self.get_response(request)

        except AuthenticationProviderInvalidTokenException:
            logger.warning(
                "Bearer token is invalid or has expired.",
                extra={"path": request.path},
            )
            return JsonResponse(
                {"error": "invalid_token", "detail": "Invalid or expired token", "status_code": 401},
                status=401,
                headers=_WWW_AUTH,
            )
        except AuthenticationProviderUnauthorizedException:
            return JsonResponse(
                {"error": "unauthorized", "detail": "Access forbidden", "status_code": 403},
                status=403,
            )
        except AuthenticationProviderUserNotFoundException:
            return JsonResponse(
                {"error": "user_not_found", "detail": "User not found", "status_code": 404},
                status=404,
            )
        except AuthenticationProviderServiceUnavailableException:
            logger.error("Authentication service is unavailable.", extra={"path": request.path})
            return JsonResponse(
                {"error": "service_unavailable", "detail": "Authentication service temporarily unavailable", "status_code": 503},
                status=503,
            )
        except AuthenticationProviderException:
            logger.exception("Authentication failed with an unexpected provider error.")
            return JsonResponse(
                {"error": "authentication_error", "detail": "Authentication error", "status_code": 500},
                status=500,
            )

    def _is_excluded(self, path: str) -> bool:
        normalised = path.rstrip("/")
        for rule in self.excluded_paths:
            rule_clean = rule.rstrip("/")
            if rule_clean.endswith("*"):
                if normalised.startswith(rule_clean[:-1]):
                    return True
            elif normalised == rule_clean:
                return True
        return False

    @staticmethod
    def _extract_token(request) -> Optional[str]:
        auth = request.headers.get("Authorization", "")
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return None
