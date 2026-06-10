from django.db import models


class PreferenceChannel(models.TextChoices):
    INAPP = "inapp", "In-app"
    EMAIL = "email", "Email"


class NotificationPreference(models.Model):
    user_id = models.BigIntegerField(primary_key=True, verbose_name="Usuario")
    inapp_enabled = models.BooleanField(default=True, verbose_name="In-app habilitado")
    email_enabled = models.BooleanField(default=True, verbose_name="Email habilitado")
    mute_until = models.DateTimeField(null=True, blank=True, verbose_name="Silenciar hasta")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_preference"
        managed = False
        verbose_name = "Preferencias de notificacion"
        verbose_name_plural = "Preferencias de notificacion"

    def __str__(self):
        return f"prefs(user={self.user_id})"
