from django.db import models


class EmailDispatchStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    SENT = "sent", "Enviado"
    FAILED = "failed", "Fallido"
    SKIPPED = "skipped", "Omitido"


class EmailDispatch(models.Model):
    id = models.BigAutoField(primary_key=True)
    receiver_id = models.BigIntegerField(db_index=True)
    event_type = models.CharField(max_length=128)
    status = models.CharField(
        max_length=16,
        choices=EmailDispatchStatus.choices,
        default=EmailDispatchStatus.PENDING,
    )
    attempt = models.IntegerField(default=0)
    error = models.TextField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "email_dispatch"
        managed = False
        verbose_name = "Despacho email"
        verbose_name_plural = "Despachos email"
        ordering = ["-created_at"]

    def __str__(self):
        return f"email_dispatch(#{self.id} ->{self.receiver_id} {self.status})"
