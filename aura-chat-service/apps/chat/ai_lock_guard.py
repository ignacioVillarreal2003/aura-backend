from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from asgiref.sync import sync_to_async

from apps.chat.ai_reply_lock import refresh, release, try_acquire
from apps.chat.exceptions import ChatAiReplyInProgressException

logger = logging.getLogger(__name__)

_REFRESH_INTERVAL_SECONDS = 30.0


async def _refresh_loop(chat_id: int, token: str) -> None:
    try:
        while True:
            await asyncio.sleep(_REFRESH_INTERVAL_SECONDS)
            await sync_to_async(refresh)(chat_id, token)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning(
            "AI reply lock refresh loop failed.",
            extra={"chat_id": chat_id},
            exc_info=True,
        )


@contextlib.asynccontextmanager
async def ai_reply_lock_guard(chat_id: int) -> AsyncIterator[str]:
    from apps.artifact_message.services.message_service import broadcast_chat_ai_lock_change

    token = await sync_to_async(try_acquire)(chat_id)
    if not token:
        raise ChatAiReplyInProgressException()

    await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, True)
    refresh_task = asyncio.create_task(_refresh_loop(chat_id, token))
    try:
        yield token
    finally:
        refresh_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await refresh_task
        await sync_to_async(release)(chat_id, token)
        await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, False)
