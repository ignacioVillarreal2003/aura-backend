from django.db import models

from core.models import AuditModel, SoftDeleteModel


class PeerMessage(AuditModel, SoftDeleteModel):
    """A human-to-human message inside a chat (no AI involved).

    Lives alongside the AI conversation (``artifact`` / ``artifact_message``) but is
    scoped to the chat's human members only. Access is gated purely by active
    membership in the parent chat.
    """

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
