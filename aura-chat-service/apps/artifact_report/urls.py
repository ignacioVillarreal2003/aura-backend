from django.urls import path

from apps.artifact_report.views import (
    ReportDetailView,
    ReportExportMarkdownView,
    ReportExportPDFView,
    ReportGenerateView,
    ReportListView,
    ReportManageExportMarkdownView,
    ReportManageExportPDFView,
    ReportManageView,
)

urlpatterns = [
    path("", ReportListView.as_view(), name="report-list"),
    path("manage/", ReportManageView.as_view(), name="report-manage"),
    path("manage/<int:report_id>/export/pdf/", ReportManageExportPDFView.as_view(), name="report-manage-export-pdf"),
    path("manage/<int:report_id>/export/markdown/", ReportManageExportMarkdownView.as_view(),
         name="report-manage-export-markdown"),
    path("generate/", ReportGenerateView.as_view(), name="report-generate"),
    path("<int:report_id>/", ReportDetailView.as_view(), name="report-detail"),
    path("<int:report_id>/export/pdf/", ReportExportPDFView.as_view(), name="report-export-pdf"),
    path("<int:report_id>/export/markdown/", ReportExportMarkdownView.as_view(), name="report-export-markdown"),
]
