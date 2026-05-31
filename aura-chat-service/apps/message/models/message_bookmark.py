from django.db import models


class MessageBookmark(models.Model):
    message = models.ForeignKey(
        "ChatMessage",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    user_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "message_bookmark"
        constraints = [
            models.UniqueConstraint(fields=["message", "user_id"], name="uq_message_bookmark"),
        ]
        indexes = [
            models.Index(fields=["message"], name="idx_message_bookmark_message"),
            models.Index(fields=["user_id"], name="idx_message_bookmark_user"),
        ]
