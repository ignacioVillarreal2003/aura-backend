import logging
from asgiref.sync import sync_to_async

from apps.artifact.models import Artifact
from core.ws.group_broadcast import asend_to_chat_group, send_to_chat_group

logger = logging.getLogger(__name__)


def _resolve_artifact_title(artifact: Artifact) -> str:
    from apps.artifact.serializers import _get_type_title

    return _get_type_title(artifact)


async def broadcast_artifact_progress(chat_id: int, step: str, message: str) -> None:
    await asend_to_chat_group(
        chat_id,
        {"type": "ai_progress", "step": step, "message": message},
    )


async def broadcast_artifact_created(chat_id: int, artifact: Artifact) -> None:
    try:
        title = await sync_to_async(_resolve_artifact_title)(artifact)
    except Exception:
        logger.warning(
            "Failed to broadcast artifact_created for chat %d", chat_id, exc_info=True
        )
        return
    await asend_to_chat_group(
        chat_id,
        {
            "type": "artifact_created",
            "artifact_id": artifact.id,
            "artifact_type": artifact.type,
            "title": title,
            "created_by": artifact.created_by,
            "created_at": artifact.created_at.isoformat(),
        },
    )


def broadcast_artifact_deleted(chat_id: int, artifact_id: int, deleted_by: int) -> None:
    send_to_chat_group(
        chat_id,
        {
            "type": "artifact_deleted",
            "artifact_id": artifact_id,
            "deleted_by": deleted_by,
        },
    )
