import logging

import redis as redis_lib
from django.conf import settings
from django.db import OperationalError, connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@extend_schema(
    tags=["Health"],
    summary="Health check",
    description="Liveness probe + dependency reachability for DB, Redis and Celery broker.",
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
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    checks: dict[str, str] = {}

    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except OperationalError:
        checks["database"] = "error"

    try:
        client = redis_lib.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    try:
        from kombu import Connection

        with Connection(settings.CELERY_BROKER_URL, connect_timeout=2) as conn:
            conn.ensure_connection(max_retries=1)
        checks["broker"] = "ok"
    except Exception:
        checks["broker"] = "error"

    all_ok = all(value == "ok" for value in checks.values())
    return Response(
        {"status": "ok" if all_ok else "degraded", "checks": checks},
        status=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
