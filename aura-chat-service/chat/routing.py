from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('api/v1/ws/chats/<int:chat_id>', consumers.ChatConsumer.as_asgi()),
]
