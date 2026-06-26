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
from core.authentication.request_token import reset_request_token, set_request_token

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

        # S2S API Key authentication check (takes priority)
        if "X-Service-Api-Key" in request.headers:
            try:
                service_user = authentication_provider.evaluate_service_auth(request)
                if service_user is not None:
                    request.authenticated_user = service_user
                    logger.debug(
                        "Request authenticated via service API key.",
                        extra={"path": request.path},
                    )
                    return self.get_response(request)
            except ServiceAuthenticationRejected as e:
                return JsonResponse(
                    {"error": e.error_code, "detail": e.detail, "status_code": e.status_code},
                    status=e.status_code,
                )

        token = self._extract_token(request)
        if not token:
            logger.warning(
                "Protected route called without credentials.",
                extra={"path": request.path},
            )
            return JsonResponse(
                {
                    "error": "missing_token",
                    "detail": "Authentication required",
                    "status_code": 401,
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
                {"error": "invalid_token", "detail": "Invalid or expired token", "status_code": 401},
                status=401,
                headers=_WWW_AUTH,
            )
        except AuthenticationProviderUnauthorizedException as e:
            logger.warning(
                "Access was forbidden by the authentication service.",
                extra={"path": request.path, "error": str(e)},
            )
            return JsonResponse(
                {"error": "unauthorized", "detail": "Access forbidden", "status_code": 403},
                status=403,
            )
        except AuthenticationProviderUserNotFoundException as e:
            logger.warning(
                "No user was found for this token.",
                extra={"path": request.path, "error": str(e)},
            )
            return JsonResponse(
                {"error": "user_not_found", "detail": "User not found", "status_code": 404},
                status=404,
            )
        except AuthenticationProviderServiceUnavailableException as e:
            logger.error(
                "Authentication service is unavailable.",
                extra={"path": request.path, "error": str(e)},
            )
            return JsonResponse(
                {
                    "error": "service_unavailable",
                    "detail": "Authentication service temporarily unavailable",
                    "status_code": 503,
                },
                status=503,
            )
        except AuthenticationProviderException as e:
            logger.exception(
                "Authentication failed with an unexpected provider error.",
                extra={"path": request.path, "error": str(e)},
            )
            return JsonResponse(
                {"error": "authentication_error", "detail": "Authentication error", "status_code": 500},
                status=500,
            )
        except Exception:
            logger.exception(
                "Unexpected error while processing authentication.",
                extra={"path": request.path},
            )
            return JsonResponse(
                {"error": "internal_error", "detail": "Internal server error", "status_code": 500},
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
