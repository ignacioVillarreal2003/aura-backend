import logging
from django.conf import settings
from django.http import JsonResponse

from core.authentication.authentication_exceptions import (
    AuthenticationProviderException,
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException,
)
from core.authentication.authentication_provider import authentication_provider
from core.authentication.request_token import reset_request_token, set_request_token
from core.middleware.correlation_id import get_correlation_id

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

        token = self._extract_token(request)
        if not token:
            logger.warning(
                "Protected route called without credentials.",
                extra={"path": request.path},
            )
            return JsonResponse(
                {
                    "detail": "Authentication required",
                    "error": "missing_token",
                    "correlation_id": get_correlation_id(),
                },
                status=401,
                headers=_WWW_AUTH,
            )

        return self._validate_jwt(request, token)

    def _validate_jwt(self, request, token: str):
        try:
            authenticated_user = authentication_provider.validate_token(token)
            request.authenticated_user = authenticated_user
            logger.debug(
                "Request authenticated with a valid bearer token.",
                extra={"user_id": authenticated_user.id, "path": request.path},
            )
            ctx = set_request_token(token)
            try:
                return self.get_response(request)
            finally:
                reset_request_token(ctx)
        except AuthenticationProviderInvalidTokenException as e:
            logger.warning(
                "Bearer token is invalid or has expired.",
                extra={"path": request.path, "error": str(e)},
            )
            return JsonResponse(
                {"detail": "Invalid or expired token", "error": "invalid_token",
                 "correlation_id": get_correlation_id()},
                status=401,
                headers=_WWW_AUTH,
            )
        except AuthenticationProviderUnauthorizedException as e:
            logger.warning(
                "Access was forbidden by the authentication service.",
                extra={"path": request.path, "error": str(e)},
            )
            return JsonResponse(
                {"detail": "Access forbidden", "error": "unauthorized", "correlation_id": get_correlation_id()},
                status=403,
            )
        except AuthenticationProviderUserNotFoundException as e:
            logger.warning(
                "No user was found for this token.",
                extra={"path": request.path, "error": str(e)},
            )
            return JsonResponse(
                {"detail": "User not found", "error": "user_not_found", "correlation_id": get_correlation_id()},
                status=404,
            )
        except AuthenticationProviderServiceUnavailableException as e:
            logger.error(
                "Authentication service is unavailable.",
                extra={"path": request.path, "error": str(e)},
            )
            return JsonResponse(
                {
                    "detail": "Authentication service temporarily unavailable",
                    "error": "service_unavailable",
                    "correlation_id": get_correlation_id(),
                },
                status=503,
            )
        except AuthenticationProviderException as e:
            logger.exception(
                "Authentication failed with an unexpected provider error.",
                extra={"path": request.path, "error": str(e)},
            )
            return JsonResponse(
                {"detail": "Authentication error", "error": "authentication_error",
                 "correlation_id": get_correlation_id()},
                status=500,
            )
        except Exception:
            logger.exception(
                "Unexpected error while processing authentication.",
                extra={"path": request.path},
            )
            return JsonResponse(
                {"detail": "Internal server error", "error": "internal_error", "correlation_id": get_correlation_id()},
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
        if auth:
            logger.warning(
                "Authorization header is present but not in Bearer format.",
                extra={"path": request.path},
            )
        return None
