"""WSGI config for notificationservice project."""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'notificationservice.settings')

application = get_wsgi_application()
