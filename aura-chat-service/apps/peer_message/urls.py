from django.urls import path

from apps.peer_message.views import PeerMessageDetailView, PeerMessageListView

urlpatterns = [
    path("", PeerMessageListView.as_view(), name="peer-message-list"),
    path("<int:message_id>/", PeerMessageDetailView.as_view(), name="peer-message-detail"),
]
