import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.artifact.models import Artifact

logger = logging.getLogger(__name__)


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
        await channel_layer.group_send(
            f"chat_{chat_id}",
            {
                "type": "artifact_created",
                "artifact_id": artifact.id,
                "artifact_type": artifact.type,
                "title": artifact.title,
                "created_by": artifact.created_by,
                "created_at": artifact.created_at.isoformat(),
            },
        )
    except Exception:
        logger.warning(
            "Failed to broadcast artifact_created for chat %d", chat_id, exc_info=True
        )


def broadcast_artifact_updated(chat_id: int, artifact: Artifact) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {
                "type": "artifact_updated",
                "artifact_id": artifact.id,
                "artifact_type": artifact.type,
                "title": artifact.title,
                "updated_by": artifact.updated_by,
                "updated_at": artifact.updated_at.isoformat() if artifact.updated_at else None,
            },
        )
    except Exception:
        logger.warning(
            "Failed to broadcast artifact_updated for chat %d", chat_id, exc_info=True
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
