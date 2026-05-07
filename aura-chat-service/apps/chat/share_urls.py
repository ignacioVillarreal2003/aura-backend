from django.urls import path

from apps.chat.views.public_share_view import PublicShareMessagesView

urlpatterns = [
    path("", PublicShareMessagesView.as_view(), name="public-share-messages"),
]
