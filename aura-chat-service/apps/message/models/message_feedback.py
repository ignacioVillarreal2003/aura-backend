from django.db import models


class MessageFeedback(models.Model):
    class Value(models.IntegerChoices):
        THUMBS_UP = 1, "Thumbs Up"
        THUMBS_DOWN = -1, "Thumbs Down"

    class Reason(models.TextChoices):
        INCORRECT = "incorrect", "Información incorrecta"
        INCOMPLETE = "incomplete", "Respuesta incompleta"
        OFF_TOPIC = "off_topic", "No responde lo que pregunté"
        TONE = "tone", "Tono o estilo inadecuado"
        TOO_LONG = "too_long", "Demasiado larga o verbosa"
        HALLUCINATION = "hallucination", "Inventó datos"
        OTHER = "other", "Otro"

    message = models.ForeignKey(
        "ChatMessage",
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    user_id = models.BigIntegerField()
    value = models.SmallIntegerField(choices=Value.choices)
    reason = models.CharField(max_length=32, choices=Reason.choices, null=True, blank=True)
    comment = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "message_feedback"
        constraints = [
            models.UniqueConstraint(fields=["message", "user_id"], name="uq_message_feedback"),
            models.CheckConstraint(
                condition=models.Q(value__in=[1, -1]),
                name="chk_feedback_value",
            ),
        ]
        indexes = [
            models.Index(fields=["message"], name="idx_message_feedback_message"),
        ]
