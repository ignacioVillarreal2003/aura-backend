import hmac
import logging
from collections import Counter
from django.conf import settings
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView


class _InternalEndpointThrottle(SimpleRateThrottle):
    scope = "internal"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


from apps.notification.api.serializers import (
    EventEmissionRequestSerializer,
    EventEmissionResponseSerializer,
)
from core.openapi.common import standard_error_responses
from apps.notification.models import EmailDispatchStatus, PreferenceChannel
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

    pending_email = sum(
        1
        for outcome in outcomes
        if outcome.channels.get(PreferenceChannel.EMAIL) == EmailDispatchStatus.PENDING
    )
    return {
        "created": sum(1 for outcome in outcomes if outcome.notification_id),
        "skipped": counts.get(EmailDispatchStatus.SKIPPED, 0),
        "pending_email": pending_email,
    }


@extend_schema(tags=["Internal"])
class InternalEventEmissionView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [_InternalEndpointThrottle]

    @extend_schema(
        summary="Emitir evento de notificación",
        description=(
            "Endpoint para microservicios productores. Recibe un evento semántico y lo despacha "
            "a uno o varios usuarios según sus preferencias globales (in-app y/o email).\n\n"
            "**Autenticación:** cabecera `X-Internal-Token`."
        ),
        request=EventEmissionRequestSerializer,
        responses={
            201: EventEmissionResponseSerializer,
            **standard_error_responses(400, 401, 429),
        },
        auth=[{"InternalToken": []}],
        examples=[
            OpenApiExample(
                "Notificación de chat",
                value={
                    "event_type": "chat.member.invited",
                    "recipient_ids": [10, 20, 30],
                    "actor_id": 5,
                    "actor_name": "admin.user",
                    "context": {"chat_id": 99, "chat_name": "Equipo de diseño"},
                },
                request_only=True,
            ),
            OpenApiExample(
                "Email de seguridad",
                value={
                    "event_type": "auth.password.changed",
                    "recipient_ids": [42],
                    "context": {
                        "recipient_email": "usuario@ejemplo.com",
                        "recipient_name": "Usuario Ejemplo",
                    },
                },
                request_only=True,
            ),
            OpenApiExample(
                "Respuesta exitosa",
                value={
                    "event_type": "chat.member.invited",
                    "created": 2,
                    "skipped": 0,
                    "pending_email": 0,
                    "outcomes": [
                        {"receiver_id": 10, "notification_id": 501, "channels": {"inapp": "sent"}},
                        {"receiver_id": 20, "notification_id": 502, "channels": {"inapp": "sent"}},
                    ],
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
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
            link_url=data.get("link_url"),
        )

        summary = _summarise(outcomes)
        body = {
            "event_type": data["event_type"],
            "outcomes": [outcome.to_dict() for outcome in outcomes],
            **summary,
        }
        return Response(body, status=status.HTTP_201_CREATED)
