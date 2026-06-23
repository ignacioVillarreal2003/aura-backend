from django.urls import path

from apps.artifact_checklist.views import (
    ChecklistDetailView,
    ChecklistExportMarkdownView,
    ChecklistExportPDFView,
    ChecklistGenerateView,
    ChecklistItemUpdateView,
    ChecklistListView,
    ChecklistManageExportMarkdownView,
    ChecklistManageExportPDFView,
    ChecklistManageView,
)

urlpatterns = [
    path("", ChecklistListView.as_view(), name="checklist-list"),
    path("manage/", ChecklistManageView.as_view(), name="checklist-manage"),
    path("<int:checklist_id>/items/<int:item_id>/", ChecklistItemUpdateView.as_view(), name="checklist-item-update"),
    path("manage/<int:checklist_id>/export/pdf/", ChecklistManageExportPDFView.as_view(),
         name="checklist-manage-export-pdf"),
    path("manage/<int:checklist_id>/export/markdown/", ChecklistManageExportMarkdownView.as_view(),
         name="checklist-manage-export-markdown"),
    path("generate/", ChecklistGenerateView.as_view(), name="checklist-generate"),
    path("<int:checklist_id>/", ChecklistDetailView.as_view(), name="checklist-detail"),
    path("<int:checklist_id>/export/pdf/", ChecklistExportPDFView.as_view(), name="checklist-export-pdf"),
    path("<int:checklist_id>/export/markdown/", ChecklistExportMarkdownView.as_view(),
         name="checklist-export-markdown"),
]
