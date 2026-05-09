from django.db import models
from core.models import CreatedAuditModel, SoftDeleteModel


class ChatMessage(CreatedAuditModel, SoftDeleteModel):
    class SenderType(models.TextChoices):
        SYSTEM = "system", "System"
        USER = "user", "User"

    chat = models.ForeignKey(
        "chat.Chat",
        on_delete=models.CASCADE,
        related_name="messages",
    )
    message = models.TextField()
    sender_type = models.CharField(max_length=64, choices=SenderType.choices)

    class Meta:
        db_table = "chat_message"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["chat"], name="idx_chat_message_chat_id"),
            models.Index(fields=["chat", "-created_at"], name="idx_chat_message_chat_created"),
        ]

    def __str__(self):
        return f"[{self.sender_type}] {self.message[:50]}"
