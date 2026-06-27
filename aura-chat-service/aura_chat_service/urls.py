from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from core.health.views import liveness, readiness, startup

urlpatterns = [
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # `/api/v1/health` kept as a backward-compatible alias of the readiness probe.
    path("api/v1/health", readiness, name="health-check"),
    path("api/v1/health/live", liveness, name="health-live"),
    path("api/v1/health/ready", readiness, name="health-ready"),
    path("api/v1/health/startup", startup, name="health-startup"),
    path("api/v1/chats/", include("apps.chat.urls")),
    path("api/v1/messages/", include("apps.artifact_message.urls")),
    path("api/v1/chats/<int:chat_id>/peer-messages/", include("apps.peer_message.urls")),
    path("api/v1/chats/<int:chat_id>/members/", include("apps.membership.urls")),
    path("api/v1/memberships/me/", include("apps.membership.me_urls")),
    path(
        "api/v1/internal/chats/<int:chat_id>/members/",
        include("apps.membership.internal_urls"),
    ),
    path("api/v1/share/<uuid:token>/messages/", include("apps.chat.share_urls")),
    path("api/v1/reports/", include("apps.artifact_report.urls")),
    path("api/v1/checklists/", include("apps.artifact_checklist.urls")),
    path("api/v1/timelines/", include("apps.artifact_timeline.urls")),
    path("api/v1/quizzes/", include("apps.artifact_quiz.urls")),
    path("api/v1/lessons-learned/", include("apps.artifact_lessons_learned.urls")),
    path("api/v1/decision-briefs/", include("apps.artifact_decision_brief.urls")),
    path("api/v1/document-summaries/", include("apps.artifact_document_summary.urls")),
    path("api/v1/document-actions/", include("apps.artifact_document_action.urls")),
    path("api/v1/assistants/", include("apps.assistant.urls")),
    path("api/v1/artifacts/", include("apps.artifact.urls")),
    path("", include("django_prometheus.urls")),
]
