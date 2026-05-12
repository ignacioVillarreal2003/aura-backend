from __future__ import annotations
import json
import logging
import time
from typing import Iterator
from django.conf import settings
from django.http import StreamingHttpResponse
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.authorization import AccessControl
from core.openapi.common import standard_error_responses
from core.authorization.permissions import NOTIFICATION_STREAM_SUBSCRIBE
from core.pubsub import subscribe_user_events

logger = logging.getLogger(__name__)


def _format_sse(event: str, data: dict | None = None) -> bytes:
    parts = [f"event: {event}"]
    if data is not None:
        body = json.dumps(data, default=str)
        for line in body.splitlines() or [""]:
            parts.append(f"data: {line}")
    parts.append("")
    parts.append("")
    return ("\n".join(parts)).encode("utf-8")


def _stream(user_id: int) -> Iterator[bytes]:
    heartbeat = float(getattr(settings, "NOTIFICATION_SSE_HEARTBEAT_SECONDS", 15))
    max_duration = float(getattr(settings, "NOTIFICATION_SSE_MAX_DURATION_SECONDS", 60 * 30))
    started = time.monotonic()

    yield _format_sse("stream.opened", {"user_id": user_id})

    try:
        for payload in subscribe_user_events(user_id, heartbeat_seconds=heartbeat):
            if time.monotonic() - started > max_duration:
                yield _format_sse("stream.closed", {"reason": "max_duration"})
                return
            if payload is None:
                yield b": keepalive\n\n"
                continue
            event_name = payload.get("event") or "notification.update"
            yield _format_sse(event_name, payload.get("data") or {})
    except GeneratorExit:
        return
    except Exception:
        logger.exception("SSE stream crashed for user %s", user_id)
        try:
            yield _format_sse("stream.error", {"detail": "internal_error"})
        finally:
            return


@extend_schema(tags=["Realtime"])
class NotificationStreamView(APIView):
    @extend_schema(
        summary="Stream de notificaciones en tiempo real (SSE)",
        description=(
            "Abre una conexión HTTP larga con respuesta `text/event-stream`. "
            "El servidor envía frames SSE cada vez que hay un cambio en la bandeja del usuario autenticado "
            "(nueva notificación, cambio de estado, eliminación).\n\n"
            "**Permiso requerido:** `NOTIFICATION_STREAM_SUBSCRIBE`\n\n"
            "**Cabeceras de la respuesta:**\n"
            "- `Content-Type: text/event-stream`\n"
            "- `Cache-Control: no-cache, no-transform`\n"
            "- `X-Accel-Buffering: no` — evita que nginx acumule el stream\n\n"
            "**Eventos que puede recibir el cliente:**\n\n"
            "| Evento | Cuándo | Contenido |\n"
            "| ------ | ------ | --------- |\n"
            "| `stream.opened` | Al conectar | `{ \"user_id\": <id> }` |\n"
            "| `notification.created` | Nueva notificación in-app | Objeto completo de la notificación |\n"
            "| `notification.updated` | Estado cambiado o mark-all-read | `{ \"id\": <id>, \"status\": \"...\" }` o `{ \"all_marked_read\": true, ... }` |\n"
            "| `notification.deleted` | Soft-delete | `{ \"id\": <id> }` |\n"
            "| `stream.closed` | Timeout de duración máxima | `{ \"reason\": \"max_duration\" }` |\n"
            "| `stream.error` | Error interno | `{ \"detail\": \"internal_error\" }` |\n\n"
            "**Heartbeats:** comentarios SSE (`: keepalive`) cada "
            f"`NOTIFICATION_SSE_HEARTBEAT_SECONDS` segundos (por defecto 15). "
            "El cliente los ignora automáticamente.\n\n"
            "**Duración máxima:** la conexión se cierra automáticamente tras "
            f"`NOTIFICATION_SSE_MAX_DURATION_SECONDS` segundos (por defecto 1800 = 30 min). "
            "El cliente debe reconectar al recibir `stream.closed`.\n\n"
            "**Sin SSE abierta:** las notificaciones siguen persistidas en la base de datos. "
            "Usar `GET /api/v1/notifications/` como fuente de verdad al iniciar la app.\n\n"
            "**Email:** el canal email **no pasa por SSE**. Los emails se procesan por "
            "RabbitMQ → Celery → SMTP de forma asíncrona."
        ),
        responses={
            200: None,
            **standard_error_responses(401, 403),
        },
        examples=[
            OpenApiExample(
                "Frame: stream abierto",
                value="event: stream.opened\ndata: {\"user_id\": 42}\n\n",
                response_only=True,
                status_codes=["200"],
                description="Primer frame enviado al establecer la conexión.",
            ),
            OpenApiExample(
                "Frame: nueva notificación",
                value=(
                    "event: notification.created\n"
                    "data: {\"id\": 123, \"message\": \"Te invitaron al chat Proyecto X\", "
                    "\"status\": \"unread\", \"severity\": \"info\", ...}\n\n"
                ),
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Frame: notificación actualizada",
                value="event: notification.updated\ndata: {\"id\": 123, \"status\": \"read\"}\n\n",
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Frame: mark-all-read",
                value='event: notification.updated\ndata: {"all_marked_read": true, "until_id": null, "count": 5}\n\n',
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Frame: notificación eliminada",
                value="event: notification.deleted\ndata: {\"id\": 123}\n\n",
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Frame: heartbeat",
                value=": keepalive\n\n",
                response_only=True,
                status_codes=["200"],
                description="Enviado periódicamente para mantener la conexión viva.",
            ),
            OpenApiExample(
                "Frame: cierre por timeout",
                value='event: stream.closed\ndata: {"reason": "max_duration"}\n\n',
                response_only=True,
                status_codes=["200"],
                description="El cliente debe abrir una nueva conexión al recibirlo.",
            ),
        ],
    )
    def get(self, request):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_STREAM_SUBSCRIBE}))

        response = StreamingHttpResponse(
            _stream(request.user.id),
            content_type="text/event-stream",
            status=status.HTTP_200_OK,
        )
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"
        return response
