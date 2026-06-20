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
    AuthenticationProviderUserNotFoundException,
)
from app.infrastructure.http.authentication_provider.interfaces.authentication_provider_interface import (
    AuthenticationProviderInterface,
)
from app.infrastructure.http.authentication_provider.request_token import set_request_token

logger = logging.getLogger(__name__)

WWW_AUTH = {
    "WWW-Authenticate": "Bearer"
}


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
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Authentication service not configured",
                    "error": "service_not_configured"
                }
            )

        token = self._extract_token(request)

        if not token:
            logger.warning(
                "Protected route called without credentials.",
                extra={
                    "path": request.url.path
                }
            )
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authentication required",
                    "error": "missing_token"
                },
                headers=WWW_AUTH
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
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Invalid or expired token",
                    "error": "invalid_token"
                },
                headers=WWW_AUTH
            )
        except AuthenticationProviderUnauthorizedException:
            logger.warning(
                "Access was forbidden by the authentication service.",
                extra={
                    "path": request.url.path,
                    "error_code": "unauthorized",
                }
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Access forbidden",
                    "error": "unauthorized"
                }
            )
        except AuthenticationProviderUserNotFoundException:
            logger.warning(
                "No user was found for this token.",
                extra={
                    "path": request.url.path,
                    "error_code": "user_not_found",
                }
            )
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "User not found",
                    "error": "user_not_found"
                }
            )
        except AuthenticationProviderServiceUnavailableException:
            logger.error(
                "Authentication service is unavailable.",
                extra={
                    "path": request.url.path,
                    "error_code": "service_unavailable",
                }
            )
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Authentication service temporarily unavailable",
                    "error": "service_unavailable"
                }
            )
        except AuthenticationProviderException:
            logger.exception(
                "Authentication failed with an unexpected provider error.",
                extra={
                    "path": request.url.path,
                    "error_code": "authentication_error",
                }
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Authentication error",
                    "error": "authentication_error"
                }
            )
        except Exception:
            logger.exception(
                "Unexpected error while processing authentication.",
                extra={
                    "path": request.url.path
                }
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error": "internal_error"
                }
            )

    def _is_excluded(
            self,
            path: str
    ) -> bool:
        normalised = path.rstrip("/")
        for rule in self.excluded_paths:
            rule = rule.rstrip("/")
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
