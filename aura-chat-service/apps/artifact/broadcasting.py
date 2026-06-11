import logging
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer

from apps.artifact.models import Artifact

logger = logging.getLogger(__name__)


def _resolve_artifact_title(artifact: Artifact) -> str:
    from apps.artifact.serializers import _get_type_title

    return _get_type_title(artifact)


async def broadcast_artifact_progress(chat_id: int, step: str, message: str) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        await channel_layer.group_send(
            f"chat_{chat_id}",
            {"type": "ai_progress", "step": step, "message": message},
        )
    except Exception:
        logger.warning(
            "Failed to broadcast artifact_progress for chat %d", chat_id, exc_info=True
        )


async def broadcast_artifact_created(chat_id: int, artifact: Artifact) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        title = await sync_to_async(_resolve_artifact_title)(artifact)
        await channel_layer.group_send(
            f"chat_{chat_id}",
            {
                "type": "artifact_created",
                "artifact_id": artifact.id,
                "artifact_type": artifact.type,
                "title": title,
                "created_by": artifact.created_by,
                "created_at": artifact.created_at.isoformat(),
            },
        )
    except Exception:
        logger.warning(
            "Failed to broadcast artifact_created for chat %d", chat_id, exc_info=True
        )


def broadcast_artifact_deleted(chat_id: int, artifact_id: int, deleted_by: int) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {
                "type": "artifact_deleted",
                "artifact_id": artifact_id,
                "deleted_by": deleted_by,
            },
        )
    except Exception:
        logger.warning(
            "Failed to broadcast artifact_deleted for chat %d", chat_id, exc_info=True
        )
