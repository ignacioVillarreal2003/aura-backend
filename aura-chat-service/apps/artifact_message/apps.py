import atexit
import asyncio

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
            pass

        def _close_llm_client():
            from core.clients.llm_client import llm_client
            try:
                asyncio.run(llm_client.aclose())
            except Exception:
                pass

        atexit.register(_close_llm_client)
