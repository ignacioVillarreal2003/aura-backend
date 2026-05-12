import logging
from django.conf import settings
from django.http import JsonResponse

from core.authentication.authentication_exceptions import (
    AuthenticationProviderException,
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException,
    ServiceAuthenticationRejected,
)
from core.authentication.authentication_provider import authentication_provider

logger = logging.getLogger(__name__)

_WWW_AUTH = {"WWW-Authenticate": "Bearer"}


class AuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        excluded_paths: list[str] = getattr(settings, "AUTHENTICATION_EXCLUDED_PATHS", [])

        if request.method == "OPTIONS":
            return self.get_response(request)

        if self._is_excluded(request.path, excluded_paths):
            request.authenticated_user = None
            return self.get_response(request)

        try:
            service_user = authentication_provider.evaluate_service_auth(request)
        except ServiceAuthenticationRejected as e:
            return JsonResponse(
                {"detail": e.detail, "error": e.error},
                status=e.status_code,
            )

        if service_user is not None:
            request.authenticated_user = service_user
            return self.get_response(request)

        token = self._extract_token(request)
        if not token:
            return JsonResponse(
                {"detail": "Authentication required", "error": "missing_token"},
                status=401,
                headers=_WWW_AUTH,
            )

        return self._validate_jwt(request, token)

    def _validate_jwt(self, request, token: str):
        try:
            authenticated_user = authentication_provider.validate_token(token)
            request.authenticated_user = authenticated_user
            return self.get_response(request)
        except AuthenticationProviderInvalidTokenException:
            return JsonResponse(
                {"detail": "Invalid or expired token", "error": "invalid_token"},
                status=401,
                headers=_WWW_AUTH,
            )
        except AuthenticationProviderUnauthorizedException:
            return JsonResponse(
                {"detail": "Access forbidden", "error": "unauthorized"},
                status=403,
            )
        except AuthenticationProviderUserNotFoundException:
            return JsonResponse(
                {"detail": "User not found", "error": "user_not_found"},
                status=404,
            )
        except AuthenticationProviderServiceUnavailableException:
            return JsonResponse(
                {
                    "detail": "Authentication service temporarily unavailable",
                    "error": "service_unavailable",
                },
                status=503,
            )
        except AuthenticationProviderException:
            logger.exception("Unhandled authentication provider error.")
            return JsonResponse(
                {"detail": "Authentication error", "error": "authentication_error"},
                status=500,
            )
        except Exception:
            logger.exception("Unexpected authentication error.")
            return JsonResponse(
                {"detail": "Internal server error", "error": "internal_error"},
                status=500,
            )

    @staticmethod
    def _is_excluded(path: str, excluded_paths: list[str]) -> bool:
        normalised = path.rstrip("/")
        for rule in excluded_paths:
            rule_clean = rule.rstrip("/")
            if rule_clean.endswith("*"):
                if normalised.startswith(rule_clean[:-1]):
                    return True
            elif normalised == rule_clean:
                return True
        return False

    @staticmethod
    def _extract_token(request) -> str | None:
        auth = request.headers.get("Authorization", "")
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return None
