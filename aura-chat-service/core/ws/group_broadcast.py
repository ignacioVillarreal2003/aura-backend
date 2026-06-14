import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def _chat_group(chat_id: int) -> str:
    return f"chat_{chat_id}"


def _log_failure(payload: dict, chat_id: int) -> None:
    logger.warning(
        "Failed to broadcast %s for chat %d",
        payload.get("type", "event"),
        chat_id,
        exc_info=True,
    )


def send_to_chat_group(chat_id: int, payload: dict) -> None:
    """Best-effort sync broadcast of ``payload`` to a chat's WS group.

    No-ops when no channel layer is configured and swallows transport errors
    (a failed fan-out must never break the request that triggered it).
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(_chat_group(chat_id), payload)
    except Exception:
        _log_failure(payload, chat_id)


async def asend_to_chat_group(chat_id: int, payload: dict) -> None:
    """Async counterpart of :func:`send_to_chat_group`."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        await channel_layer.group_send(_chat_group(chat_id), payload)
    except Exception:
        _log_failure(payload, chat_id)
