from django.db import models
from core.models import AuditModel, SoftDeleteModel


class ChatMembership(AuditModel, SoftDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        PENDING = "pending", "Pending"

    member_id = models.BigIntegerField()
    chat = models.ForeignKey(
        "chat.Chat",
        on_delete=models.CASCADE,
        related_name="chatmembership",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["member_id", "chat"],
                condition=models.Q(deleted_at__isnull=True),
                name="chat_membership_member_chat_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["chat"], name="idx_chat_membership_chat_id"),
            models.Index(fields=["member_id"], name="idx_chat_membership_member"),
            models.Index(
                fields=["chat", "member_id", "status"],
                name="idx_chat_membership_chat_member_status",
            ),
        ]

    def __str__(self):
        return f"Member {self.member_id} in Chat {self.chat_id} ({self.status})"
