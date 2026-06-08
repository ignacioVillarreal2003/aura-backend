import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aura_chat_service.settings.production")

django_asgi_app = get_asgi_application()

from apps.chat.routing import websocket_urlpatterns
from core.authentication.websocket_auth_middleware import WebSocketAuthMiddleware

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": WebSocketAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        ),
    }
)
