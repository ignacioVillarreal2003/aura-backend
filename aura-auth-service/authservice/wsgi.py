"""
WSGI config for authservice project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'authservice.settings')

application = get_wsgi_application()
