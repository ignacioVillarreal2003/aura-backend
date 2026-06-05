from django.urls import path

from apps.artifact_timeline.views import (
    TimelineDetailView,
    TimelineExportMarkdownView,
    TimelineExportPDFView,
    TimelineGenerateView,
    TimelineListView,
    TimelineManageExportMarkdownView,
    TimelineManageExportPDFView,
    TimelineManageView,
)

urlpatterns = [
    path("", TimelineListView.as_view(), name="timeline-list"),
    path("manage/", TimelineManageView.as_view(), name="timeline-manage"),
    path("manage/<int:timeline_id>/export/pdf/", TimelineManageExportPDFView.as_view(),
         name="timeline-manage-export-pdf"),
    path("manage/<int:timeline_id>/export/markdown/", TimelineManageExportMarkdownView.as_view(),
         name="timeline-manage-export-markdown"),
    path("generate/", TimelineGenerateView.as_view(), name="timeline-generate"),
    path("<int:timeline_id>/", TimelineDetailView.as_view(), name="timeline-detail"),
    path("<int:timeline_id>/export/pdf/", TimelineExportPDFView.as_view(), name="timeline-export-pdf"),
    path("<int:timeline_id>/export/markdown/", TimelineExportMarkdownView.as_view(),
         name="timeline-export-markdown"),
]
