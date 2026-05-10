"""Server-Sent Events stream of notification deltas.

Auth: standard `Authorization: Bearer <jwt>`. The middleware validates
the token once when the connection opens; every subsequent frame is
delivered without re-validating (the cache TTL controls staleness if
the token expires mid-stream).

Wire format:

    event: notification.created
    data: {"id": 42, "message": "...", ...}

    : keepalive

The view publishes a final `event: stream.closed` before terminating
when the maximum duration is reached (defaults to 30 minutes), allowing
the client to reconnect cleanly.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Iterator

from django.conf import settings
from django.http import StreamingHttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notification.api.serializers import ErrorResponseSerializer
from core.authorization import AccessControl
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
        # Client disconnected.
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
        summary="Server-Sent Events stream",
        description=(
            "Long-lived `text/event-stream` connection that pushes "
            "`notification.created`, `notification.updated` and "
            "`notification.deleted` events for the authenticated user. "
            "Heartbeats every "
            f"{getattr(settings, 'NOTIFICATION_SSE_HEARTBEAT_SECONDS', 15)} seconds."
        ),
        responses={200: None, 401: ErrorResponseSerializer},
    )
    def get(self, request):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_STREAM_SUBSCRIBE}))

        response = StreamingHttpResponse(
            _stream(request.user.id),
            content_type="text/event-stream",
            status=status.HTTP_200_OK,
        )
        response["Cache-Control"] = "no-cache, no-transform"
        response["X-Accel-Buffering"] = "no"  # disable nginx proxy buffering
        return response
