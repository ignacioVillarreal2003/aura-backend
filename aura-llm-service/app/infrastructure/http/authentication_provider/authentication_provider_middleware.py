import json
import logging
from typing import Optional
from starlette.types import ASGIApp, Receive, Scope, Send

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
from app.infrastructure.http.authentication_provider.request_token import reset_request_token, set_request_token

logger = logging.getLogger(__name__)

_AUTHORIZATION_HEADER = b"authorization"


async def _send_error(
        send: Send,
        request_id: Optional[str],
        status_code: int,
        error: str,
        message: str,
        *,
        www_authenticate: bool = False,
) -> None:
    content: dict = {"error": error, "message": message}
    if request_id:
        content["request_id"] = request_id
    body = json.dumps(content, ensure_ascii=False).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("latin-1")),
    ]
    if www_authenticate:
        headers.append((b"www-authenticate", b"Bearer"))
    if request_id:
        headers.append((b"x-request-id", request_id.encode("latin-1")))
    await send({"type": "http.response.start", "status": status_code, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class AuthenticationProviderMiddleware:
    def __init__(
            self,
            app: ASGIApp,
            excluded_paths: Optional[list[str]] = None,
    ) -> None:
        self.app = app
        self.excluded_paths: list[str] = excluded_paths or []

    async def __call__(
            self,
            scope: Scope,
            receive: Receive,
            send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if self._is_excluded(path):
            logger.debug(
                "Skipping authentication for this path.",
                extra={
                    "path": path
                }
            )
            await self.app(scope, receive, send)
            return

        request_id = (scope.get("state") or {}).get("request_id")
        app_state = scope["app"].state

        provider: Optional[AuthenticationProviderInterface] = getattr(
            app_state, "authentication_provider", None
        )
        if provider is None:
            logger.error(
                "Authentication provider is not configured on the application.",
                extra={
                    "path": path
                }
            )
            await _send_error(
                send, request_id, 503,
                "service_not_configured", "Authentication service not configured",
            )
            return

        token = self._extract_token(scope, path)

        if not token:
            logger.warning(
                "Protected route called without credentials.",
                extra={
                    "path": path
                }
            )
            await _send_error(
                send, request_id, 401,
                "missing_token", "Authentication required",
                www_authenticate=True,
            )
            return

        settings = getattr(app_state, "authentication_provider_settings", None)
        if settings is not None and len(token) > settings.max_bearer_token_characters:
            logger.warning(
                "Rejected a bearer token that exceeds the configured maximum length.",
                extra={
                    "path": path,
                    "error_code": "token_too_long",
                },
            )
            await _send_error(
                send, request_id, 401,
                "token_too_long", "Bearer token is too long",
                www_authenticate=True,
            )
            return

        await self._validate_jwt(scope, receive, send, token, provider, request_id, path)

    async def _validate_jwt(
            self,
            scope: Scope,
            receive: Receive,
            send: Send,
            token: str,
            authentication_provider: AuthenticationProviderInterface,
            request_id: Optional[str],
            path: str,
    ) -> None:
        try:
            authenticated_user = await authentication_provider.validate_token(token)
        except AuthenticationProviderInvalidTokenException:
            logger.warning(
                "Bearer token is invalid or has expired.",
                extra={
                    "path": path,
                    "error_code": "invalid_token",
                }
            )
            await _send_error(
                send, request_id, 401,
                "invalid_token", "Invalid or expired token",
                www_authenticate=True,
            )
            return
        except AuthenticationProviderUnauthorizedException:
            logger.warning(
                "Access was forbidden by the authentication service.",
                extra={
                    "path": path,
                    "error_code": "unauthorized",
                }
            )
            await _send_error(send, request_id, 403, "unauthorized", "Access forbidden")
            return
        except AuthenticationProviderUserNotFoundException:
            logger.warning(
                "No user was found for this token.",
                extra={
                    "path": path,
                    "error_code": "user_not_found",
                }
            )
            await _send_error(send, request_id, 404, "user_not_found", "User not found")
            return
        except AuthenticationProviderServiceUnavailableException:
            logger.error(
                "Authentication service is unavailable.",
                extra={
                    "path": path,
                    "error_code": "service_unavailable",
                }
            )
            await _send_error(
                send, request_id, 503,
                "service_unavailable", "Authentication service temporarily unavailable",
            )
            return
        except AuthenticationProviderException:
            logger.exception(
                "Authentication failed with an unexpected provider error.",
                extra={
                    "path": path,
                    "error_code": "authentication_error",
                }
            )
            await _send_error(send, request_id, 500, "authentication_error", "Authentication error")
            return
        except Exception:
            logger.exception(
                "Unexpected error while processing authentication.",
                extra={
                    "path": path
                }
            )
            await _send_error(send, request_id, 500, "internal_error", "Internal server error")
            return

        state = scope.setdefault("state", {})
        state["authenticated_user"] = AuthenticatedUser.model_validate(authenticated_user)
        bearer = token if token.lower().startswith("bearer ") else f"Bearer {token}"
        state["authorization_header_outbound"] = bearer
        context_token = set_request_token(bearer)
        logger.debug(
            "Request authenticated with a valid bearer token.",
            extra={
                "user_id": authenticated_user.id,
                "path": path
            }
        )

        try:
            await self.app(scope, receive, send)
        finally:
            reset_request_token(context_token)

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
            scope: Scope,
            path: str
    ) -> Optional[str]:
        auth = ""
        for key, value in scope.get("headers", []):
            if key.lower() == _AUTHORIZATION_HEADER:
                auth = value.decode("latin-1")
                break
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        if auth:
            logger.warning(
                "Authorization header is present but not in Bearer format.",
                extra={
                    "path": path
                }
            )
        return None
