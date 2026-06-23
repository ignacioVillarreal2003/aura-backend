from django.urls import path

from apps.artifact_quiz.views import (
    QuizDetailView,
    QuizExportMarkdownView,
    QuizExportPDFView,
    QuizGenerateView,
    QuizListView,
    QuizManageExportMarkdownView,
    QuizManageExportPDFView,
    QuizManageView,
    QuizQuestionAnswerView,
    QuizResetView,
)

urlpatterns = [
    path("", QuizListView.as_view(), name="quiz-list"),
    path("manage/", QuizManageView.as_view(), name="quiz-manage"),
    path("<int:quiz_id>/questions/<int:question_id>/answer/", QuizQuestionAnswerView.as_view(),
         name="quiz-question-answer"),
    path("<int:quiz_id>/reset/", QuizResetView.as_view(), name="quiz-reset"),
    path("manage/<int:quiz_id>/export/pdf/", QuizManageExportPDFView.as_view(), name="quiz-manage-export-pdf"),
    path("manage/<int:quiz_id>/export/markdown/", QuizManageExportMarkdownView.as_view(),
         name="quiz-manage-export-markdown"),
    path("generate/", QuizGenerateView.as_view(), name="quiz-generate"),
    path("<int:quiz_id>/", QuizDetailView.as_view(), name="quiz-detail"),
    path("<int:quiz_id>/export/pdf/", QuizExportPDFView.as_view(), name="quiz-export-pdf"),
    path("<int:quiz_id>/export/markdown/", QuizExportMarkdownView.as_view(), name="quiz-export-markdown"),
]
