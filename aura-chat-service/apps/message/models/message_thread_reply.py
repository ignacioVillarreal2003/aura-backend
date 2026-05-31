from django.db import models


class MessageThreadReply(models.Model):
    parent_message = models.ForeignKey(
        "ChatMessage",
        on_delete=models.CASCADE,
        related_name="thread_replies",
    )
    message = models.TextField()
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "message_thread_reply"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["parent_message"], name="idx_thread_reply_parent"),
        ]
