from django.urls import path

from apps.message.views.message_view import MessageListView

urlpatterns = [
    path("", MessageListView.as_view(), name="message-list"),
]
