import logging
from typing import Callable, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderException,
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException
)
from app.infrastructure.http.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface
)
from app.infrastructure.http.authentication_provider.request_token import set_request_token

logger = logging.getLogger(__name__)

WWW_AUTH = {
    "WWW-Authenticate": "Bearer"
}


def _error_response(
        request: Request,
        status_code: int,
        error: str,
        message: str,
        *,
        www_authenticate: bool = False,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    content: dict = {"error": error, "message": message}
    if request_id:
        content["request_id"] = request_id
    headers: dict = {}
    if www_authenticate:
        headers.update(WWW_AUTH)
    if request_id:
        headers["X-Request-ID"] = request_id
    return JSONResponse(status_code=status_code, content=content, headers=headers)


class AuthenticationProviderMiddleware(BaseHTTPMiddleware):
    def __init__(
            self,
            app: ASGIApp,
            excluded_paths: Optional[list[str]] = None,
    ) -> None:
        super().__init__(app)
        self.excluded_paths: list[str] = excluded_paths or []

    async def dispatch(
            self,
            request: Request,
            call_next: Callable
    ) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        if self._is_excluded(request.url.path):
            logger.debug(
                "Skipping authentication for this path.",
                extra={
                    "path": request.url.path
                }
            )
            return await call_next(request)

        provider: Optional[AuthenticationProviderInterface] = getattr(
            request.app.state, "authentication_provider", None
        )
        if provider is None:
            logger.error(
                "Authentication provider is not configured on the application.",
                extra={
                    "path": request.url.path
                }
            )
            return _error_response(
                request, 503,
                "service_not_configured", "Authentication service not configured",
            )

        token = self._extract_token(request)

        if not token:
            logger.warning(
                "Protected route called without credentials.",
                extra={
                    "path": request.url.path
                }
            )
            return _error_response(
                request, 401,
                "missing_token", "Authentication required",
                www_authenticate=True,
            )

        settings = getattr(request.app.state, "authentication_provider_settings", None)
        if settings is not None and len(token) > settings.max_bearer_token_characters:
            logger.warning(
                "Rejected a bearer token that exceeds the configured maximum length.",
                extra={
                    "path": request.url.path,
                    "error_code": "token_too_long",
                },
            )
            return _error_response(
                request, 401,
                "token_too_long", "Bearer token is too long",
                www_authenticate=True,
            )

        return await self._validate_jwt(request, call_next, token, provider)

    async def _validate_jwt(
            self,
            request: Request,
            call_next: Callable,
            token: str,
            authentication_provider: AuthenticationProviderInterface
    ) -> Response:
        try:
            authenticated_user = await authentication_provider.validate_token(token)
            request.state.authenticated_user = AuthenticatedUser.model_validate(authenticated_user)
            bearer = token if token.lower().startswith("bearer ") else f"Bearer {token}"
            request.state.authorization_header_outbound = bearer
            set_request_token(bearer)
            logger.debug(
                "Request authenticated with a valid bearer token.",
                extra={
                    "user_id": authenticated_user.id,
                    "path": request.url.path
                }
            )
            return await call_next(request)

        except AuthenticationProviderInvalidTokenException:
            logger.warning(
                "Bearer token is invalid or has expired.",
                extra={
                    "path": request.url.path,
                    "error_code": "invalid_token",
                }
            )
            return _error_response(
                request, 401,
                "invalid_token", "Invalid or expired token",
                www_authenticate=True,
            )
        except AuthenticationProviderUnauthorizedException:
            logger.warning(
                "Access was forbidden by the authentication service.",
                extra={
                    "path": request.url.path,
                    "error_code": "unauthorized",
                }
            )
            return _error_response(request, 403, "unauthorized", "Access forbidden")
        except AuthenticationProviderUserNotFoundException:
            logger.warning(
                "No user was found for this token.",
                extra={
                    "path": request.url.path,
                    "error_code": "user_not_found",
                }
            )
            return _error_response(request, 404, "user_not_found", "User not found")
        except AuthenticationProviderServiceUnavailableException:
            logger.error(
                "Authentication service is unavailable.",
                extra={
                    "path": request.url.path,
                    "error_code": "service_unavailable",
                }
            )
            return _error_response(
                request, 503,
                "service_unavailable", "Authentication service temporarily unavailable",
            )
        except AuthenticationProviderException:
            logger.exception(
                "Authentication failed with an unexpected provider error.",
                extra={
                    "path": request.url.path,
                    "error_code": "authentication_error",
                }
            )
            return _error_response(request, 500, "authentication_error", "Authentication error")
        except Exception:
            logger.exception(
                "Unexpected error while processing authentication.",
                extra={
                    "path": request.url.path
                }
            )
            return _error_response(request, 500, "internal_error", "Internal server error")

    def _is_excluded(
            self,
            path: str
    ) -> bool:
        normalised = path.rstrip("/")
        for excluded in self.excluded_paths:
            rule = excluded.rstrip("/")
            if rule.endswith("*"):
                if normalised.startswith(rule[:-1]):
                    return True
            elif normalised == rule:
                return True
        return False

    @staticmethod
    def _extract_token(
            request: Request
    ) -> Optional[str]:
        auth = request.headers.get("Authorization", "")
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        if auth:
            logger.warning(
                "Authorization header is present but not in Bearer format.",
                extra={
                    "path": request.url.path
                }
            )
        return None
