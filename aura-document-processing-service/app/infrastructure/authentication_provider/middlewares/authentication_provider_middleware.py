import logging
from typing import Optional, Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

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

        logger.info(
            "AuthenticationMiddleware initialized",
            extra={
                "excluded_paths": self.excluded_paths,
                "require_auth": self.require_auth
            }
        )

    def _is_excluded_path(
            self,
            path: str
    ) -> bool:
        path = path.rstrip('/')

        for excluded_path in self.excluded_paths:
            excluded_path = excluded_path.rstrip('/')

            if excluded_path.endswith('*'):
                prefix = excluded_path[:-1]
                if path.startswith(prefix):
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
            logger.warning(
                "Invalid authorization header format",
                extra={"path": request.url.path}
            )
            return None

        return parts[1]

    async def dispatch(
            self,
            request: Request,
            call_next: Callable
    ) -> Response:
        if self._is_excluded_path(request.url.path):
            logger.debug(
                f"Path excluded from authentication",
                extra={
                    "path": request.url.path
                }
            )
            return await call_next(request)

        token = self._extract_token(request)

        if not token:
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
                    headers={
                        "WWW-Authenticate": "Bearer"
                    }
                )
            else:
                logger.debug(
                    "No token provided, continuing without user",
                    extra={
                        "path": request.url.path
                    }
                )
                request.state.user = None
                return await call_next(request)

        try:
            auth_provider = request.app.state.authentication_provider

            user = await auth_provider.get_user_by_token(token)

            request.state.user = user

            logger.debug(
                "User authenticated successfully",
                extra={
                    "user_id": user.id,
                    "path": request.url.path
                }
            )

            response = await call_next(request)

            return response

        except AuthenticationProviderInvalidTokenException as e:
            logger.warning(
                "Invalid token provided",
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
                headers={
                    "WWW-Authenticate": "Bearer"
                }
            )

        except AuthenticationProviderUnauthorizedException as e:
            logger.warning(
                "Unauthorized access attempt",
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
            logger.error(
                "Authentication error",
                extra={
                    "path": request.url.path,
                    "error": str(e)
                },
                exc_info=True
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
                },
                exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": "Authentication service not configured",
                    "error": "service_not_configured"
                }
            )

        except Exception as e:
            logger.error(
                "Unexpected error in authentication middleware",
                extra={
                    "path": request.url.path,
                    "error_type": type(e).__name__,
                    "error": str(e)
                },
                exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "error": "internal_error"
                }
            )
