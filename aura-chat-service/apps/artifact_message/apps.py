from django.apps import AppConfig


class MessageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.artifact_message"
    verbose_name = "Message"

    def ready(self):
        try:
            from core.clients.transcription_client import _get_model
            _get_model()
        except ImportError:
            pass  # faster_whisper not installed in this environment
