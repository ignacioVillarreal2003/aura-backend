from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxLengthValidator
from django.db import models

from core.models import AuditModel, SoftDeleteModel


class Chat(AuditModel, SoftDeleteModel):
    name = models.CharField(max_length=255)
    system_prompt = models.TextField(null=True, blank=True)
    response_style = models.TextField(null=True, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    source_assistant_id = models.BigIntegerField(null=True, blank=True)
    tags = ArrayField(
        models.TextField(validators=[MaxLengthValidator(50)]),
        default=list,
        blank=True,
    )
    is_locked = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "chat"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
