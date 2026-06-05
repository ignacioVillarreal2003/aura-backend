import logging
from django.core.cache import cache as _cache
from django.db import OperationalError as DBOperationalError
from django.db import connection
from django.urls import include, path
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@extend_schema(
    tags=["Health"],
    summary="Health check",
    description=(
            "Returns `status: ok` or `degraded` and per-dependency checks (`database`, `redis`). "
            "**200** when all checks pass; **503** when any dependency fails."
    ),
    auth=[],
    responses={
        200: inline_serializer(
            name="HealthResponse",
            fields={
                "status": serializers.CharField(),
                "checks": serializers.DictField(child=serializers.CharField()),
            },
        ),
        503: inline_serializer(
            name="HealthDegradedResponse",
            fields={
                "status": serializers.CharField(),
                "checks": serializers.DictField(child=serializers.CharField()),
            },
        ),
    },
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    checks = {}

    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        logger.warning("Health check: database unreachable.", exc_info=True)
        checks["database"] = "error"

    try:
        _cache.set("_healthcheck", "ok", timeout=5)
        checks["redis"] = "ok"
    except Exception:
        logger.warning("Health check: Redis unreachable.")
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(
        {"status": "ok" if all_ok else "degraded", "checks": checks},
        status=http_status,
    )


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
    path("api/v1/health", health_check, name="health-check"),
    path("api/v1/chats/", include("apps.chat.urls")),
    path("api/v1/chats/<int:chat_id>/messages/", include("apps.artifact_message.urls")),
    path("api/v1/chats/<int:chat_id>/members/", include("apps.membership.urls")),
    path("api/v1/memberships/me/", include("apps.membership.me_urls")),
    path("api/v1/share/<uuid:token>/messages/", include("apps.chat.share_urls")),
    path("api/v1/reports/", include("apps.artifact_report.urls")),
    path("api/v1/checklists/", include("apps.artifact_checklist.urls")),
    path("api/v1/timelines/", include("apps.artifact_timeline.urls")),
    path("api/v1/quizzes/", include("apps.artifact_quiz.urls")),
    path("api/v1/lessons-learned/", include("apps.artifact_lessons_learned.urls")),
    path("api/v1/decision-briefs/", include("apps.artifact_decision_brief.urls")),
    path("api/v1/assistants/", include("apps.assistant.urls")),
    path("api/v1/artifacts/", include("apps.artifact.urls")),
    path("", include("django_prometheus.urls")),
]
