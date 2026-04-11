from django.urls import path

from . import views

urlpatterns = [
    # Chat CRUD
    path("chats", views.ChatListView.as_view(), name="chat-list"),
    path("chats/<int:chat_id>", views.ChatDetailView.as_view(), name="chat-detail"),

    # Message CRUD  —  POST returns full JSON (non-streaming)
    path("chats/<int:chat_id>/messages", views.MessageListView.as_view(), name="message-list"),
    path("chats/<int:chat_id>/messages/<int:message_id>", views.MessageDetailView.as_view(), name="message-detail"),

    # SSE streaming endpoint  —  POST streams text/event-stream
    path("chats/<int:chat_id>/messages/stream", views.SSEChatStreamView.as_view(), name="message-stream"),
]
