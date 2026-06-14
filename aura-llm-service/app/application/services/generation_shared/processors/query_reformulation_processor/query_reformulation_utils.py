from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message


def format_history_messages(history_messages_window: int, history_messages: list[Message]) -> str:
    tail = history_messages[-history_messages_window:] if history_messages_window > 0 else []
    return "\n".join(
        f"{'Usuario' if msg.role == MessageRole.human else 'Asistente'}: {msg.content}"
        for msg in tail
    )
