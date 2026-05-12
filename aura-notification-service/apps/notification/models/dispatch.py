from django.db import models


class DispatchChannel(models.TextChoices):
    INAPP = "inapp", "In-app"
    EMAIL = "email", "Email"


class DispatchStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    SENT = "sent", "Enviado"
    FAILED = "failed", "Fallido"
    SKIPPED = "skipped", "Omitido"
    SUPPRESSED = "suppressed", "Suprimido"


class NotificationDispatch(models.Model):
    id = models.BigAutoField(primary_key=True)
    notification_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    receiver_id = models.BigIntegerField(db_index=True)
    event_type = models.CharField(max_length=128)
    channel = models.CharField(max_length=16, choices=DispatchChannel.choices)
    status = models.CharField(
        max_length=16,
        choices=DispatchStatus.choices,
        default=DispatchStatus.PENDING,
    )
    attempt = models.IntegerField(default=0)
    error = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification_dispatch"
        managed = False
        verbose_name = "Despacho"
        verbose_name_plural = "Despachos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"dispatch(#{self.id} {self.channel}->{self.receiver_id} {self.status})"
