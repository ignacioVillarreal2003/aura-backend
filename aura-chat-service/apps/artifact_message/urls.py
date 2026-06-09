from django.urls import path

from apps.artifact_message.views import (
    MessageDetailView,
    MessageExportMarkdownView,
    MessageExportPDFView,
    MessageGenerateView,
    MessageListView,
    MessageManageExportMarkdownView,
    MessageManageExportPDFView,
    MessageManageView,
)

urlpatterns = [
    path("", MessageListView.as_view(), name="message-list"),
    path("manage/", MessageManageView.as_view(), name="message-manage"),
    path("manage/<int:message_id>/export/pdf/", MessageManageExportPDFView.as_view(), name="message-manage-export-pdf"),
    path("manage/<int:message_id>/export/markdown/", MessageManageExportMarkdownView.as_view(), name="message-manage-export-markdown"),
    path("generate/", MessageGenerateView.as_view(), name="message-generate"),
    path("<int:message_id>/", MessageDetailView.as_view(), name="message-detail"),
    path("<int:message_id>/export/pdf/", MessageExportPDFView.as_view(), name="message-export-pdf"),
    path("<int:message_id>/export/markdown/", MessageExportMarkdownView.as_view(), name="message-export-markdown"),
]
