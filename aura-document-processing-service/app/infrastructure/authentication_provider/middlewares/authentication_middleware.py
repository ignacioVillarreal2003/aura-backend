import logging
from typing import Optional, Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.infrastructure.authentication_provider.dependencies.authentication_provider_dependencies import (
    get_authentication_provider
)
from app.infrastructure.authentication_provider.exceptions.authentication_provider_exception import (
    AuthenticationProviderInvalidTokenException,
    AuthenticationProviderUnauthorizedException,
    AuthenticationProviderServiceUnavailableException,
    AuthenticationProviderUserNotFoundException,
    AuthenticationProviderException
)

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(
            self,
            app: ASGIApp,
            excluded_paths: Optional[list[str]] = None,
            require_auth: bool = True
    ):
        super().__init__(app)
        self.excluded_paths = excluded_paths or []
        self.require_auth = require_auth

        logger.info("AuthenticationMiddleware initialized")

    def _is_excluded_path(
            self,
            path: str
    ) -> bool:
        path = path.rstrip('/')

        for excluded_path in self.excluded_paths:
            excluded_path = excluded_path.rstrip('/')

            if excluded_path.endswith('*'):
                if path.startswith(excluded_path[:-1]):
                    return True
            elif path == excluded_path:
                return True

        return False

    def _extract_token(
            self,
            request: Request
    ) -> Optional[str]:
        authorization = request.headers.get("Authorization")

        if not authorization:
            return None

        parts = authorization.split()

        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning("Invalid authorization header format")
            return None

        return parts[1]

    async def dispatch(
            self,
            request: Request,
            call_next: Callable
    ) -> Response:
        if self._is_excluded_path(request.url.path):
            logger.debug(f"Path {request.url.path} is excluded from authentication")
            return await call_next(request)

        token = self._extract_token(request)

        if not token:
            if self.require_auth:
                logger.warning(f"No token provided for {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Authentication required",
                        "error": "missing_token"
                    }
                )
            else:
                logger.debug("No token provided, continuing without user")
                request.state.user = None
                return await call_next(request)

        try:
            auth_provider = get_authentication_provider()

            user = await auth_provider.get_user_by_token(token)

            request.state.user = user

            logger.debug(f"User {user.id} authenticated for {request.url.path}")

            response = await call_next(request)

            return response

        except AuthenticationProviderInvalidTokenException as e:
            logger.warning(f"Invalid token for {request.url.path}: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": str(e),
                    "error": "invalid_token"
                }
            )

        except AuthenticationProviderUnauthorizedException as e:
            logger.warning(f"Unauthorized access to {request.url.path}: {e}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": str(e),
                    "error": "unauthorized"
                }
            )

        except AuthenticationProviderUserNotFoundException as e:
            logger.warning(f"User not found for {request.url.path}: {e}")
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "detail": str(e),
                    "error": "user_not_found"
                }
            )

        except AuthenticationProviderServiceUnavailableException as e:
            logger.error(f"Auth service unavailable for {request.url.path}: {e}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": "Authentication service temporarily unavailable",
                    "error": "service_unavailable"
                }
            )

        except AuthenticationProviderException as e:
            logger.error(f"Authentication error for {request.url.path}: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Authentication error",
                    "error": "authentication_error"
                }
            )

        except Exception as e:
            logger.error(
                f"Unexpected error in authentication middleware for {request.url.path}: {e}",
                exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "error": "internal_error"
                }
            )
