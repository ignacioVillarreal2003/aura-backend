import logging
from typing import Callable, List, Optional
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.infrastructure.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderException,
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderUserNotFoundException
)

logger = logging.getLogger(__name__)

_WWW_AUTH_HEADER = {"WWW-Authenticate": "Bearer"}


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(
            self,
            app: ASGIApp,
            excluded_paths: Optional[List[str]] = None,
            require_auth: bool = True
    ) -> None:
        super().__init__(app)
        self.excluded_paths: List[str] = excluded_paths or []
        self.require_auth: bool = require_auth

    async def dispatch(
            self,
            request: Request,
            call_next: Callable
    ) -> Response:
        if self._is_excluded_path(request.url.path):
            logger.debug(
                "Path excluded from authentication",
                extra={
                    "path": request.url.path
                }
            )
            return await call_next(request)

        token = self._extract_token(request)

        if not token:
            return await self._handle_missing_token(request, call_next)

        return await self._authenticate(request, call_next, token)

    async def _authenticate(
            self,
            request: Request,
            call_next: Callable,
            token: str
    ) -> Response:
        try:
            auth_provider = request.app.state.authentication_provider
            user = await auth_provider.validate_token(token)
            request.state.user = user

            logger.debug(
                "User authenticated successfully",
                extra={
                    "user_id": user.id,
                    "path": request.url.path
                }
            )

            return await call_next(request)

        except AuthenticationProviderInvalidTokenException as e:
            logger.warning(
                "Invalid token rejected",
                extra={
                    "path": request.url.path,
                    "error": str(e)
                }
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid or expired token",
                    "error": "invalid_token"
                },
                headers=_WWW_AUTH_HEADER,
            )

        except AuthenticationProviderUnauthorizedException as e:
            logger.warning(
                "Forbidden access attempt",
                extra={
                    "path": request.url.path,
                    "error": str(e)
                }
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "Access forbidden",
                    "error": "unauthorized"
                }
            )

        except AuthenticationProviderUserNotFoundException as e:
            logger.warning(
                "User not found",
                extra={
                    "path": request.url.path,
                    "error": str(e)
                }
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "detail": "User not found",
                    "error": "user_not_found"
                }
            )

        except AuthenticationProviderServiceUnavailableException as e:
            logger.error(
                "Authentication service unavailable",
                extra={
                    "path": request.url.path,
                    "error": str(e)
                }
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": "Authentication service temporarily unavailable",
                    "error": "service_unavailable"
                }
            )

        except AuthenticationProviderException as e:
            logger.exception(
                "Authentication error",
                extra={
                    "path": request.url.path,
                    "error": str(e)
                }
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Authentication error",
                    "error": "authentication_error"
                }
            )

        except AttributeError as e:
            logger.error(
                "AuthenticationProvider not found in app.state",
                extra={
                    "path": request.url.path,
                    "error": str(e)
                }
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": "Authentication service not configured",
                    "error": "service_not_configured"
                }
            )

        except Exception as e:
            logger.exception(
                "Unexpected error in authentication middleware",
                extra={
                    "path": request.url.path,
                    "error_type": type(e).__name__
                }
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "error": "internal_error"
                }
            )

    async def _handle_missing_token(
            self,
            request: Request,
            call_next: Callable
    ) -> Response:
        if self.require_auth:
            logger.warning(
                "No token provided for protected path",
                extra={
                    "path": request.url.path
                }
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Authentication required",
                    "error": "missing_token"
                },
                headers=_WWW_AUTH_HEADER,
            )

        logger.debug(
            "No token provided, continuing as unauthenticated",
            extra={
                "path": request.url.path
            }
        )
        request.state.user = None
        return await call_next(request)

    def _is_excluded_path(
            self,
            path: str
    ) -> bool:
        normalised = path.rstrip("/")

        for excluded in self.excluded_paths:
            excluded = excluded.rstrip("/")

            if excluded.endswith("*"):
                if normalised.startswith(excluded[:-1]):
                    return True
            elif normalised == excluded:
                return True

        return False

    @staticmethod
    def _extract_token(request: Request) -> Optional[str]:
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning(
                "Malformed Authorization header",
                extra={
                    "path": request.url.path
                }
            )
            return None

        return parts[1]
