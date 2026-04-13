from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.chat.views.chat_view import ChatViewSet

router = DefaultRouter()
router.register(r"", ChatViewSet, basename="chat")

urlpatterns = [
    path("", include(router.urls)),
]
