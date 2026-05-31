from django.db import models


class PinnedMessage(models.Model):
    message = models.ForeignKey(
        "ChatMessage",
        on_delete=models.CASCADE,
        related_name="pins",
    )
    chat = models.ForeignKey(
        "chat.Chat",
        on_delete=models.CASCADE,
        related_name="pinned_messages",
    )
    pinned_by = models.BigIntegerField()
    pinned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "pinned_message"
        constraints = [
            models.UniqueConstraint(
                fields=["message", "chat"],
                name="pinned_message_unique",
            )
        ]
        indexes = [
            models.Index(fields=["chat"], name="idx_pinned_message_chat"),
        ]

    def __str__(self):
        return f"Pinned message {self.message_id} in chat {self.chat_id}"
