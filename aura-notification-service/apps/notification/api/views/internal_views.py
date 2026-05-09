"""Internal service-to-service endpoints.

Authenticated by `X-Internal-Token`. Producers hit them from inside the
private network; the central Authentication middleware does not touch
these paths (configured via `AUTHENTICATION_EXCLUDED_PATHS`).
"""

import hmac
import logging
from collections import Counter

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notification.api.serializers import (
    ErrorResponseSerializer,
    EventEmissionRequestSerializer,
    EventEmissionResponseSerializer,
    LegacyAdminCreateRequestSerializer,
    LegacyAdminCreateResponseSerializer,
)
from apps.notification.models import DispatchStatus, PreferenceChannel
from apps.notification.services import notification_service

logger = logging.getLogger(__name__)


def _internal_token_ok(request) -> bool:
    expected = str(settings.NOTIFICATION_INTERNAL_API_TOKEN)
    raw = request.headers.get("X-Internal-Token", "")
    return bool(raw) and hmac.compare_digest(raw, expected)


def _summarise(outcomes) -> dict:
    counts = Counter()
    for outcome in outcomes:
        for status_value in outcome.channels.values():
            counts[status_value] += 1
        if outcome.suppressed:
            counts["__suppressed__"] += 1

    pending_email = sum(
        1
        for outcome in outcomes
        if outcome.channels.get(PreferenceChannel.EMAIL) == DispatchStatus.PENDING
    )
    return {
        "created": sum(1 for outcome in outcomes if outcome.notification_id and not outcome.suppressed),
        "suppressed": counts.get("__suppressed__", 0),
        "skipped": counts.get(DispatchStatus.SKIPPED, 0),
        "pending_email": pending_email,
    }


@extend_schema(tags=["Internal"])
class InternalEventEmissionView(APIView):
    """POST /api/v1/internal/events/ — preferred entry point for producers."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Emit a notification event",
        request=EventEmissionRequestSerializer,
        responses={
            201: EventEmissionResponseSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
        },
        auth=[{"InternalToken": []}],
    )
    def post(self, request):
        if not _internal_token_ok(request):
            return Response(
                {"detail": "Unauthorized internal call.", "error": "unauthorized"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = EventEmissionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        outcomes = notification_service.emit_event(
            event_type=data["event_type"],
            recipient_ids=data["recipient_ids"],
            actor_id=data.get("actor_id"),
            actor_name=data.get("actor_name"),
            context=data.get("context") or {},
            idempotency_key=data.get("idempotency_key"),
            link_url=data.get("link_url"),
            channels_override=data.get("channels_override"),
            target_scope=data.get("target_scope") or "individual",
            target_label=data.get("target_label"),
        )

        summary = _summarise(outcomes)
        body = {
            "event_type": data["event_type"],
            "outcomes": [outcome.to_dict() for outcome in outcomes],
            **summary,
        }
        return Response(body, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Internal"])
class LegacyAdminCreateView(APIView):
    """Back-compat endpoint kept for the aura-auth-service admin panel.

    Translates the legacy `{ receiver_ids, message, type, target_scope, ... }`
    payload into a regular `admin.broadcast` event going through the
    normal dispatcher pipeline.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Create admin broadcast notifications (legacy)",
        request=LegacyAdminCreateRequestSerializer,
        responses={
            201: LegacyAdminCreateResponseSerializer,
            401: ErrorResponseSerializer,
        },
        auth=[{"InternalToken": []}],
    )
    def post(self, request):
        if not _internal_token_ok(request):
            return Response(
                {"detail": "Unauthorized internal call.", "error": "unauthorized"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = LegacyAdminCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        outcomes = notification_service.admin_broadcast(
            receiver_ids=data["receiver_ids"],
            message=data["message"],
            actor_user_id=data.get("actor_user_id"),
            actor_name=data.get("actor_name"),
            target_scope=data.get("target_scope") or "individual",
            target_label=data.get("target_label"),
            send_email=data.get("send_email", False),
            subject=data.get("subject"),
        )
        summary = _summarise(outcomes)
        body = {
            **summary,
            "notification_ids": [
                outcome.notification_id for outcome in outcomes if outcome.notification_id
            ],
        }
        return Response(body, status=status.HTTP_201_CREATED)
