import logging

import redis as redis_lib
from django.conf import settings
from django.contrib import admin
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
    except DBOperationalError:
        logger.warning("Health check: database unreachable.")
        checks["database"] = "error"

    try:
        r = redis_lib.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        r.ping()
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
    path("admin/", admin.site.urls),
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
    path("api/v1/chats/<int:chat_id>/messages/", include("apps.message.urls")),
    path("api/v1/chats/<int:chat_id>/members/", include("apps.membership.urls")),
    path("api/v1/share/<uuid:token>/messages/", include("apps.chat.share_urls")),
    path("", include("django_prometheus.urls")),
]
