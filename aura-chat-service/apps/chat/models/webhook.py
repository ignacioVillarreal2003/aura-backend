from django.contrib.postgres.fields import ArrayField
from django.db import models


WEBHOOK_EVENTS = [
    "message.created",
    "member.joined",
    "member.left",
    "chat.locked",
    "chat.unlocked",
]


class ChatWebhook(models.Model):
    chat = models.ForeignKey(
        "Chat",
        on_delete=models.CASCADE,
        related_name="webhooks",
    )
    url = models.TextField()
    events = ArrayField(models.CharField(max_length=50), default=list)
    secret = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_webhook"
        indexes = [
            models.Index(fields=["chat"], name="idx_chat_webhook_chat"),
        ]

    def __str__(self):
        return f"Webhook {self.id} for chat {self.chat_id} → {self.url}"
