import logging
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from core.authentication.authentication_exceptions import AuthenticationProviderException
from core.authentication.authentication_provider import authentication_provider

logger = logging.getLogger(__name__)


class WebSocketAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        token_list = params.get("token", [])

        if not token_list:
            logger.warning("WebSocket connection attempted without token.")
            await send({"type": "websocket.close", "code": 4001})
            return

        token = token_list[0]

        try:
            authenticated_user = await database_sync_to_async(
                authentication_provider.validate_token
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

        return await super().__call__(scope, receive, send)
