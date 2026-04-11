"""ASGI entry point for the Aura Chat Service.

Served by Daphne.  Django Channels is no longer required because real-time
communication is now handled via Server-Sent Events (SSE) over standard HTTP,
which Django's ASGI application supports natively.

Run with:
    daphne -b 0.0.0.0 -p 8000 config.asgi:application
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# `django.setup()` is called implicitly by get_asgi_application().
from django.core.asgi import get_asgi_application  # noqa: E402

application = get_asgi_application()
