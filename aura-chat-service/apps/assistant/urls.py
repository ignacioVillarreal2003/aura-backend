from django.urls import path

from apps.assistant.views import (
    AssistantDetailView,
    AssistantListCreateView,
    AssistantManageView,
    AssistantStartChatView,
)

urlpatterns = [
    path("", AssistantListCreateView.as_view(), name="assistant-list-create"),
    path("manage/", AssistantManageView.as_view(), name="assistant-manage"),
    path("<int:assistant_id>/", AssistantDetailView.as_view(), name="assistant-detail"),
    path("<int:assistant_id>/start-chat/", AssistantStartChatView.as_view(), name="assistant-start-chat"),
]
