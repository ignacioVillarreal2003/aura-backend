from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.chat.views.chat_view import ChatViewSet
from apps.chat.views.share_link_view import ShareLinkDetailView, ShareLinkListView

router = DefaultRouter()
router.register(r"", ChatViewSet, basename="chat")

urlpatterns = [
    path("", include(router.urls)),
    path("<int:chat_id>/share-links/", ShareLinkListView.as_view(), name="share-link-list"),
    path("<int:chat_id>/share-links/<int:link_id>/", ShareLinkDetailView.as_view(), name="share-link-detail"),
]
