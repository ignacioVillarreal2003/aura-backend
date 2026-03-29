import logging
from typing import Callable, List, Optional
from fastapi import HTTPException, Request, Response
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

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    _WWW_AUTH = {"WWW-Authenticate": "Bearer"}

    def __init__(
        self,
        app: ASGIApp,
        excluded_paths: Optional[List[str]] = None,
        require_auth: bool = True,
    ) -> None:
        super().__init__(app)
        self.excluded_paths: List[str] = excluded_paths or []
        self.require_auth = require_auth

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._is_excluded(request.url.path):
            logger.debug("Path excluded from auth", extra={"path": request.url.path})
            return await call_next(request)

        try:
            provider = request.app.state.authentication_provider
        except AttributeError:
            logger.error("authentication_provider not found in app.state", extra={"path": request.url.path})
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication service not configured", "error": "service_not_configured"},
            )

        try:
            s2s_user = provider.evaluate_service_auth(request)
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content=e.detail)

        if s2s_user is not None:
            request.state.authenticated_user = s2s_user
            logger.debug("S2S auth accepted", extra={"user_id": s2s_user.id, "path": request.url.path})
            return await call_next(request)

        token = self._extract_token(request)

        if not token:
            if self.require_auth:
                logger.warning("No credentials on protected path", extra={"path": request.url.path})
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required", "error": "missing_token"},
                    headers=self._WWW_AUTH,
                )
            logger.debug("No credentials, continuing unauthenticated", extra={"path": request.url.path})
            request.state.authenticated_user = None
            return await call_next(request)

        return await self._validate_jwt(request, call_next, token)

    async def _validate_jwt(self, request: Request, call_next: Callable, token: str) -> Response:
        try:
            provider = request.app.state.authentication_provider
            authenticated_user = await provider.validate_token(token)
            request.state.authenticated_user = AuthenticatedUser.model_validate(authenticated_user)
            logger.debug("JWT auth accepted", extra={"user_id": authenticated_user.id, "path": request.url.path})
            return await call_next(request)

        except AuthenticationProviderInvalidTokenException as e:
            logger.warning("Invalid token", extra={"path": request.url.path, "error": str(e)})
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token", "error": "invalid_token"},
                headers=self._WWW_AUTH,
            )
        except AuthenticationProviderUnauthorizedException as e:
            logger.warning("Forbidden", extra={"path": request.url.path, "error": str(e)})
            return JSONResponse(status_code=403, content={"detail": "Access forbidden", "error": "unauthorized"})
        except AuthenticationProviderUserNotFoundException as e:
            logger.warning("User not found", extra={"path": request.url.path, "error": str(e)})
            return JSONResponse(status_code=404, content={"detail": "User not found", "error": "user_not_found"})
        except AuthenticationProviderServiceUnavailableException as e:
            logger.error("Auth service unavailable", extra={"path": request.url.path, "error": str(e)})
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication service temporarily unavailable", "error": "service_unavailable"},
            )
        except AuthenticationProviderException as e:
            logger.exception("Auth provider error", extra={"path": request.url.path, "error": str(e)})
            return JSONResponse(status_code=500, content={"detail": "Authentication error", "error": "authentication_error"})
        except Exception:
            logger.exception("Unexpected middleware error", extra={"path": request.url.path})
            return JSONResponse(status_code=500, content={"detail": "Internal server error", "error": "internal_error"})

    def _is_excluded(self, path: str) -> bool:
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
    def _extract_token(request: Request) -> Optional[str]:
        auth = request.headers.get("Authorization", "")
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        if auth:
            logger.warning("Malformed Authorization header", extra={"path": request.url.path})
        return None
