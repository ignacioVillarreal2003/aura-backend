from apps.artifact_message.models import ArtifactMessage
from apps.artifact_message.repositories.message_repository import message_repository


def build_chat_history(chat_id: int, limit: int = 20) -> list[dict]:
    recent = message_repository.get_recent_messages(chat_id, limit=limit)
    recent.reverse()
    return [
        {
            "role": "human" if msg.sender_type == ArtifactMessage.SenderType.USER else "assistant",
            "content": msg.message,
        }
        for msg in recent
    ]
