import logging
import redis as redis_lib
from django.conf import settings
from django.db import OperationalError, connection
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@extend_schema(
    tags=["Health"],
    summary="Health check",
    description=(
        "Liveness probe y verificación de dependencias externas. "
        "Comprueba la conectividad a la base de datos PostgreSQL, Redis y el broker RabbitMQ.\n\n"
        "**No requiere autenticación.** Diseñado para ser consumido por balanceadores de carga, "
        "orquestadores (Kubernetes liveness/readiness probes) y sistemas de monitoreo.\n\n"
        "**Lógica de respuesta:**\n"
        "- `200 OK` — todas las dependencias responden correctamente (`status: ok`).\n"
        "- `503 Service Unavailable` — al menos una dependencia falló (`status: degraded`). "
        "El campo `checks` identifica cuál o cuáles fallaron con el valor `error`.\n\n"
        "**Timeouts por dependencia:** cada check tiene un timeout de 2 segundos para no bloquear "
        "el probe. Una dependencia lenta se reporta como `error`.\n\n"
        "**Campos de `checks`:**\n"
        "- `database`: conectividad a PostgreSQL (`ok` / `error`).\n"
        "- `redis`: conectividad a Redis (`ok` / `error`).\n"
        "- `broker`: conectividad al broker AMQP / RabbitMQ (`ok` / `error`)."
    ),
    auth=[],
    responses={
        200: inline_serializer(
            name="HealthResponse",
            fields={
                "status": serializers.CharField(
                    help_text="Estado global del servicio. `ok` si todas las dependencias están disponibles."
                ),
                "checks": serializers.DictField(
                    child=serializers.CharField(),
                    help_text=(
                        "Estado individual por dependencia. Claves posibles: `database`, `redis`, `broker`. "
                        "Valores: `ok` o `error`."
                    ),
                ),
            },
        ),
        503: inline_serializer(
            name="HealthDegradedResponse",
            fields={
                "status": serializers.CharField(
                    help_text="Estado global del servicio. `degraded` si al menos una dependencia falló."
                ),
                "checks": serializers.DictField(
                    child=serializers.CharField(),
                    help_text="Estado individual por dependencia. La(s) dependencia(s) fallida(s) tendrán valor `error`.",
                ),
            },
        ),
    },
    examples=[
        OpenApiExample(
            "Todas las dependencias OK",
            value={"status": "ok", "checks": {"database": "ok", "redis": "ok", "broker": "ok"}},
            response_only=True,
            status_codes=["200"],
            description="El servicio está completamente operativo.",
        ),
        OpenApiExample(
            "Redis caído",
            value={"status": "degraded", "checks": {"database": "ok", "redis": "error", "broker": "ok"}},
            response_only=True,
            status_codes=["503"],
            description="La base de datos y el broker responden, pero Redis no está disponible.",
        ),
        OpenApiExample(
            "Múltiples dependencias caídas",
            value={"status": "degraded", "checks": {"database": "error", "redis": "error", "broker": "ok"}},
            response_only=True,
            status_codes=["503"],
            description="Base de datos y Redis no responden. El broker sigue operativo.",
        ),
    ],
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
        try:
            client.ping()
            checks["redis"] = "ok"
        finally:
            client.close()
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
