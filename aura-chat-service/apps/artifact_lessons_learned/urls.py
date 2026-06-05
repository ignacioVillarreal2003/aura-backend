from django.urls import path

from apps.artifact_lessons_learned.views import (
    LessonsLearnedDetailView,
    LessonsLearnedExportMarkdownView,
    LessonsLearnedExportPDFView,
    LessonsLearnedGenerateView,
    LessonsLearnedListView,
    LessonsLearnedManageExportMarkdownView,
    LessonsLearnedManageExportPDFView,
    LessonsLearnedManageView,
)

urlpatterns = [
    path("", LessonsLearnedListView.as_view(), name="lessons-learned-list"),
    path("manage/", LessonsLearnedManageView.as_view(), name="lessons-learned-manage"),
    path("manage/<int:lessons_learned_id>/export/pdf/", LessonsLearnedManageExportPDFView.as_view(),
         name="lessons-learned-manage-export-pdf"),
    path("manage/<int:lessons_learned_id>/export/markdown/", LessonsLearnedManageExportMarkdownView.as_view(),
         name="lessons-learned-manage-export-markdown"),
    path("generate/", LessonsLearnedGenerateView.as_view(), name="lessons-learned-generate"),
    path("<int:lessons_learned_id>/", LessonsLearnedDetailView.as_view(), name="lessons-learned-detail"),
    path("<int:lessons_learned_id>/export/pdf/", LessonsLearnedExportPDFView.as_view(),
         name="lessons-learned-export-pdf"),
    path("<int:lessons_learned_id>/export/markdown/", LessonsLearnedExportMarkdownView.as_view(),
         name="lessons-learned-export-markdown"),
]
