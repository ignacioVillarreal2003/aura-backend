from django.db import models


class PreferenceChannel(models.TextChoices):
    INAPP = "inapp", "In-app"
    EMAIL = "email", "Email"


class NotificationPreference(models.Model):
    user_id = models.BigIntegerField(primary_key=True, verbose_name="Usuario")
    inapp_enabled = models.BooleanField(default=True, verbose_name="In-app habilitado")
    email_enabled = models.BooleanField(default=True, verbose_name="Email habilitado")
    mute_until = models.DateTimeField(null=True, blank=True, verbose_name="Silenciar hasta")

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.BigIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    updated_by = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "notification_preference"
        managed = False
        verbose_name = "Preferencias de notificacion"
        verbose_name_plural = "Preferencias de notificacion"

    def __str__(self):
        return f"prefs(user={self.user_id})"


class NotificationEventPreference(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_id = models.BigIntegerField(db_index=True)
    event_type = models.CharField(max_length=128)
    channel = models.CharField(max_length=16, choices=PreferenceChannel.choices)
    enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    updated_by = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "notification_event_preference"
        managed = False
        verbose_name = "Preferencia por evento"
        verbose_name_plural = "Preferencias por evento"
        unique_together = ("user_id", "event_type", "channel")

    def __str__(self):
        flag = "on" if self.enabled else "off"
        return f"event_pref(user={self.user_id} {self.event_type}:{self.channel}={flag})"
