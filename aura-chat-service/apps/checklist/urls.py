from django.urls import path

from apps.checklist.views import (
    ChecklistDetailView,
    ChecklistExportMarkdownView,
    ChecklistExportPDFView,
    ChecklistListCreateView,
)

urlpatterns = [
    path("", ChecklistListCreateView.as_view(), name="checklist-list-create"),
    path("<int:checklist_id>/", ChecklistDetailView.as_view(), name="checklist-detail"),
    path("<int:checklist_id>/export/pdf/", ChecklistExportPDFView.as_view(), name="checklist-export-pdf"),
    path("<int:checklist_id>/export/markdown/", ChecklistExportMarkdownView.as_view(), name="checklist-export-markdown"),
]
