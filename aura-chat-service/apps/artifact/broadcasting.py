import logging

from channels.layers import get_channel_layer

from apps.artifact.models import Artifact

logger = logging.getLogger(__name__)


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
