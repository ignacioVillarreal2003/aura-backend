from django.urls import path

from apps.artifact_decision_brief.views import (
    DecisionBriefDetailView,
    DecisionBriefExportMarkdownView,
    DecisionBriefExportPDFView,
    DecisionBriefGenerateView,
    DecisionBriefListView,
    DecisionBriefManageExportMarkdownView,
    DecisionBriefManageExportPDFView,
    DecisionBriefManageView,
)

urlpatterns = [
    path("", DecisionBriefListView.as_view(), name="decision-brief-list"),
    path("manage/", DecisionBriefManageView.as_view(), name="decision-brief-manage"),
    path("manage/<int:decision_brief_id>/export/pdf/", DecisionBriefManageExportPDFView.as_view(),
         name="decision-brief-manage-export-pdf"),
    path("manage/<int:decision_brief_id>/export/markdown/", DecisionBriefManageExportMarkdownView.as_view(),
         name="decision-brief-manage-export-markdown"),
    path("generate/", DecisionBriefGenerateView.as_view(), name="decision-brief-generate"),
    path("<int:decision_brief_id>/", DecisionBriefDetailView.as_view(), name="decision-brief-detail"),
    path("<int:decision_brief_id>/export/pdf/", DecisionBriefExportPDFView.as_view(),
         name="decision-brief-export-pdf"),
    path("<int:decision_brief_id>/export/markdown/", DecisionBriefExportMarkdownView.as_view(),
         name="decision-brief-export-markdown"),
]
