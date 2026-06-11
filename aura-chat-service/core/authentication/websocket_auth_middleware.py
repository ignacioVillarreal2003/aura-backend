import logging
from urllib.parse import parse_qs
from asgiref.sync import sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings

from core.authentication.authentication_exceptions import AuthenticationProviderException
from core.authentication.authentication_provider import authentication_provider
from core.authentication.request_token import reset_request_token, set_request_token

logger = logging.getLogger(__name__)


def _get_header(scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("utf-8", errors="replace")
    return None


def _is_origin_allowed(origin: str) -> bool:
    allowed = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
    return origin.rstrip("/") in [o.rstrip("/") for o in allowed]


class WebSocketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        origin = _get_header(scope, b"origin")
        if origin is not None and not _is_origin_allowed(origin):
            logger.warning(
                "WebSocket connection rejected: origin not allowed.",
                extra={"origin": origin},
            )
            await send({"type": "websocket.close", "code": 4003})
            return

        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        token_list = params.get("token", [])

        if not token_list:
            logger.warning("WebSocket connection attempted without token.")
            await send({"type": "websocket.close", "code": 4001})
            return

        token = token_list[0]

        try:
            authenticated_user = await sync_to_async(
                authentication_provider.validate_token, thread_sensitive=False
            )(token)
            scope["user"] = authenticated_user
            logger.debug(
                "WebSocket authenticated.",
                extra={"user_id": authenticated_user.id},
            )
        except AuthenticationProviderException:
            logger.warning("WebSocket authentication failed.")
            await send({"type": "websocket.close", "code": 4003})
            return
        except Exception:
            logger.exception("Unexpected error during WebSocket authentication.")
            await send({"type": "websocket.close", "code": 4003})
            return

        ctx = set_request_token(token)
        try:
            return await super().__call__(scope, receive, send)
        finally:
            reset_request_token(ctx)
