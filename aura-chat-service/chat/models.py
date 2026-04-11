from django.db import models
from django.utils import timezone


class Chat(models.Model):
    name = models.CharField(max_length=255)
    system_prompt = models.TextField(null=True, blank=True)
    response_style = models.TextField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'chat'

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self, deleted_by):
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save()


class MembershipStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    PENDING = 'pending', 'Pending'


class ChatMembership(models.Model):
    member_id = models.BigIntegerField()
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='memberships')
    status = models.CharField(
        max_length=20,
        choices=MembershipStatus.choices,
        default=MembershipStatus.ACTIVE,
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)

    created_by = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'chat_membership'
        unique_together = [['member_id', 'chat']]

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class SenderType(models.TextChoices):
    SYSTEM = 'system', 'System'
    USER = 'user', 'User'


class ChatMessage(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    message = models.TextField()
    sender_type = models.CharField(max_length=10, choices=SenderType.choices)

    created_by = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_by = models.BigIntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'chat_message'

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self, deleted_by):
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save()
