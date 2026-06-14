from django.apps import AppConfig
from django.conf import settings


class ChatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.chat"
    verbose_name = "Chat"

    def ready(self):
        if getattr(settings, "WHISPER_PRELOAD", False):
            from core.clients.transcription_client import preload_model_in_background
            preload_model_in_background()
