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
        # Always throttle by IP regardless of token validity — prevents brute-force
        # on NOTIFICATION_INTERNAL_API_TOKEN.
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


from apps.notification.api.serializers import (
    EventEmissionRequestSerializer,
    EventEmissionResponseSerializer,
)
from core.openapi.common import standard_error_responses
from apps.notification.models import DispatchStatus, PreferenceChannel, TargetScope
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
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [_InternalEndpointThrottle]

    @extend_schema(
        summary="Emitir evento de notificación",
        description=(
            "Endpoint para microservicios productores. Recibe un evento semántico y lo despacha "
            "a uno o varios usuarios según sus preferencias de canal (in-app y/o email).\n\n"
            "**Autenticación:** cabecera `X-Internal-Token` con el valor de `NOTIFICATION_INTERNAL_API_TOKEN`. "
            "Esta ruta está excluida del middleware JWT. El token se valida con comparación en tiempo "
            "constante para evitar timing attacks.\n\n"
            "**Throttle:** 120 req/minuto por IP.\n\n"
            "**Flujo de despacho por receptor:**\n"
            "1. Si el evento no es silenciable (`is_silenceable: false`): se entrega siempre.\n"
            "2. Si el usuario tiene mute activo: se suprime.\n"
            "3. Si el canal global está deshabilitado: se suprime para ese canal.\n"
            "4. Si hay override por evento: se usa ese valor.\n"
            "5. Si no hay override: se usan los canales por defecto del evento.\n\n"
            "**Optimización:** incluir `recipient_email` en `context` evita un round-trip "
            "al servicio de autenticación para obtener el email del destinatario."
        ),
        request=EventEmissionRequestSerializer,
        responses={
            201: EventEmissionResponseSerializer,
            **standard_error_responses(400, 401, 429),
        },
        auth=[{"InternalToken": []}],
        examples=[
            OpenApiExample(
                "Notificación de chat a múltiples usuarios",
                value={
                    "event_type": "chat.member.invited",
                    "recipient_ids": [10, 20, 30],
                    "actor_id": 5,
                    "actor_name": "admin.user",
                    "context": {"chat_id": 99, "chat_name": "Equipo de diseño"},
                    "idempotency_key": "chat-99-invite-batch-2026-05",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Email de seguridad con email en context",
                value={
                    "event_type": "auth.password.changed",
                    "recipient_ids": [42],
                    "context": {
                        "recipient_email": "usuario@ejemplo.com",
                        "recipient_name": "Usuario Ejemplo",
                    },
                },
                request_only=True,
                description="Incluir recipient_email evita un round-trip al auth service.",
            ),
            OpenApiExample(
                "Forzar solo email",
                value={
                    "event_type": "document.processing.failed",
                    "recipient_ids": [7],
                    "context": {"document_id": 303, "recipient_email": "usuario@ejemplo.com"},
                    "channels_override": ["email"],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Anuncio administrativo",
                value={
                    "event_type": "admin.broadcast",
                    "recipient_ids": [1, 2, 3, 4, 5],
                    "actor_name": "Equipo Aura",
                    "context": {"message": "Mantenimiento programado el viernes a las 22:00 hs."},
                    "target_scope": "broadcast",
                    "target_label": "Mantenimiento Mayo 2026",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Respuesta exitosa — 2 creadas, 1 suprimida",
                value={
                    "event_type": "chat.member.invited",
                    "created": 2,
                    "suppressed": 1,
                    "skipped": 0,
                    "pending_email": 0,
                    "outcomes": [
                        {"receiver_id": 10, "notification_id": 501, "channels": {"inapp": "sent"}, "suppressed": False},
                        {"receiver_id": 20, "notification_id": 502, "channels": {"inapp": "sent"}, "suppressed": False},
                        {"receiver_id": 30, "notification_id": 500, "channels": {"inapp": "suppressed"}, "suppressed": True},
                    ],
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Respuesta exitosa — con email encolado",
                value={
                    "event_type": "auth.password.changed",
                    "created": 1,
                    "suppressed": 0,
                    "skipped": 0,
                    "pending_email": 1,
                    "outcomes": [
                        {
                            "receiver_id": 42,
                            "notification_id": 601,
                            "channels": {"inapp": "sent", "email": "pending"},
                            "suppressed": False,
                        }
                    ],
                },
                response_only=True,
                status_codes=["201"],
            ),
            OpenApiExample(
                "Token inválido",
                value={"detail": "Unauthorized internal call.", "error": "unauthorized"},
                response_only=True,
                status_codes=["401"],
            ),
            OpenApiExample(
                "Tipo de evento desconocido",
                value={"error": "bad_request", "detail": "Validation failed", "status_code": 400, "fields": {"event_type": ["Unknown event_type 'evento.inexistente'."]}},
                response_only=True,
                status_codes=["400"],
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
            idempotency_key=data.get("idempotency_key"),
            title=data.get("title"),
            link_url=data.get("link_url"),
            channels_override=data.get("channels_override"),
            target_scope=data.get("target_scope") or TargetScope.INDIVIDUAL,
            target_label=data.get("target_label"),
        )

        summary = _summarise(outcomes)
        body = {
            "event_type": data["event_type"],
            "outcomes": [outcome.to_dict() for outcome in outcomes],
            **summary,
        }
        return Response(body, status=status.HTTP_201_CREATED)
