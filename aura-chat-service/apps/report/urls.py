from django.urls import path

from apps.report.views import (
    ReportDetailView,
    ReportExportMarkdownView,
    ReportExportPDFView,
    ReportListCreateView,
)

urlpatterns = [
    path("", ReportListCreateView.as_view(), name="report-list-create"),
    path("<int:report_id>/", ReportDetailView.as_view(), name="report-detail"),
    path("<int:report_id>/export/pdf/", ReportExportPDFView.as_view(), name="report-export-pdf"),
    path("<int:report_id>/export/markdown/", ReportExportMarkdownView.as_view(), name="report-export-markdown"),
]
