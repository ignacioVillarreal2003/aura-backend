"""Celery application factory.

The worker is started with:

    celery -A aura_notification_service worker -l info

It picks up tasks from any module named `tasks.py` (or `tasks/` package) inside
`INSTALLED_APPS`, e.g. `apps.notification.tasks.send_email`.
"""

import os

from celery import Celery

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "aura_notification_service.settings.production",
)

app = Celery("aura_notification_service")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
