from django.urls import path

from apps.artifact_document_summary.views import (
    DocumentSummaryDetailView,
    DocumentSummaryExportMarkdownView,
    DocumentSummaryExportPDFView,
    DocumentSummaryGenerateView,
    DocumentSummaryListView,
    DocumentSummaryManageExportMarkdownView,
    DocumentSummaryManageExportPDFView,
    DocumentSummaryManageView,
)

urlpatterns = [
    path("", DocumentSummaryListView.as_view(), name="document-summary-list"),
    path("manage/", DocumentSummaryManageView.as_view(), name="document-summary-manage"),
    path("manage/<int:document_summary_id>/export/pdf/", DocumentSummaryManageExportPDFView.as_view(),
         name="document-summary-manage-export-pdf"),
    path("manage/<int:document_summary_id>/export/markdown/", DocumentSummaryManageExportMarkdownView.as_view(),
         name="document-summary-manage-export-markdown"),
    path("generate/", DocumentSummaryGenerateView.as_view(), name="document-summary-generate"),
    path("<int:document_summary_id>/", DocumentSummaryDetailView.as_view(), name="document-summary-detail"),
    path("<int:document_summary_id>/export/pdf/", DocumentSummaryExportPDFView.as_view(),
         name="document-summary-export-pdf"),
    path("<int:document_summary_id>/export/markdown/", DocumentSummaryExportMarkdownView.as_view(),
         name="document-summary-export-markdown"),
]
