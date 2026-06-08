from django.urls import path

from apps.artifact_document_action.views import (
    DocumentActionDetailView,
    DocumentActionExportMarkdownView,
    DocumentActionExportPDFView,
    DocumentActionGenerateView,
    DocumentActionListView,
    DocumentActionManageExportMarkdownView,
    DocumentActionManageExportPDFView,
    DocumentActionManageView,
)

urlpatterns = [
    path("", DocumentActionListView.as_view(), name="document-action-list"),
    path("manage/", DocumentActionManageView.as_view(), name="document-action-manage"),
    path("manage/<int:document_action_id>/export/pdf/", DocumentActionManageExportPDFView.as_view(),
         name="document-action-manage-export-pdf"),
    path("manage/<int:document_action_id>/export/markdown/", DocumentActionManageExportMarkdownView.as_view(),
         name="document-action-manage-export-markdown"),
    path("generate/", DocumentActionGenerateView.as_view(), name="document-action-generate"),
    path("<int:document_action_id>/", DocumentActionDetailView.as_view(), name="document-action-detail"),
    path("<int:document_action_id>/export/pdf/", DocumentActionExportPDFView.as_view(),
         name="document-action-export-pdf"),
    path("<int:document_action_id>/export/markdown/", DocumentActionExportMarkdownView.as_view(),
         name="document-action-export-markdown"),
]
