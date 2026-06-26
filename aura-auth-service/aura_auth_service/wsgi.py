"""
WSGI config for aura_auth_service project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aura_auth_service.settings.development')

application = get_wsgi_application()
