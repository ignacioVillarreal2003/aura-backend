import os
from celery import Celery

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "aura_notification_service.settings.development",
)

app = Celery("aura_notification_service")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
