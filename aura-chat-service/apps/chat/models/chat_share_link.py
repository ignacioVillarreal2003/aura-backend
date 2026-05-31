import uuid
from django.db import models


class ChatShareLink(models.Model):
    chat = models.ForeignKey(
        "Chat",
        on_delete=models.CASCADE,
        related_name="share_links",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        managed = False
        db_table = "chat_share_link"
        indexes = [
            models.Index(fields=["chat"], name="idx_share_link_chat"),
            models.Index(fields=["token"], name="idx_share_link_token"),
        ]
