from django.db import models

from core.models import AuditModel, SoftDeleteModel


class PeerMessage(AuditModel, SoftDeleteModel):

    message = models.TextField(max_length=10000)
    chat = models.ForeignKey(
        "chat.Chat",
        on_delete=models.CASCADE,
        related_name="peer_messages",
    )

    class Meta:
        managed = False
        db_table = "chat_peer_message"
        ordering = ["-created_at"]

    def __str__(self):
        return f"PeerMessage {self.pk} in Chat {self.chat_id}"
