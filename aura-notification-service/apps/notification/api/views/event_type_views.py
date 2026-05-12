from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notification.api.serializers import EventTypeCatalogueEntrySerializer
from apps.notification.events import iter_events


@extend_schema(tags=["Event Types"])
class EventTypeCatalogueView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Catálogo de tipos de evento",
        description=(
            "Devuelve la lista completa de tipos de evento soportados por el servicio. "
            "No requiere autenticación.\n\n"
            "Útil para armar pantallas de configuración de preferencias sin necesitar un JWT. "
            "Para ver el estado efectivo por canal del usuario autenticado, "
            "usar `GET /api/v1/me/notification-preferences/event-types/`.\n\n"
            "**Campos relevantes:**\n"
            "- `default_channels`: canales activos por defecto si el usuario no tiene overrides.\n"
            "- `available_channels`: canales que el usuario puede configurar.\n"
            "- `is_silenceable`: si es `false`, el evento se entrega siempre ignorando "
            "preferencias del usuario (mute, quiet hours, canal deshabilitado)."
        ),
        auth=[],
        responses={200: EventTypeCatalogueEntrySerializer(many=True)},
        examples=[
            OpenApiExample(
                "Respuesta exitosa",
                value=[
                    {
                        "event_type": "chat.member.invited",
                        "type": "event",
                        "severity": "info",
                        "description": "Te invitaron a un chat.",
                        "default_channels": ["inapp"],
                        "available_channels": ["inapp", "email"],
                        "is_silenceable": True,
                    },
                    {
                        "event_type": "auth.password.changed",
                        "type": "system",
                        "severity": "critical",
                        "description": "Cambio de contrasena exitoso.",
                        "default_channels": ["inapp", "email"],
                        "available_channels": ["inapp", "email"],
                        "is_silenceable": False,
                    },
                    {
                        "event_type": "document.processing.failed",
                        "type": "event",
                        "severity": "critical",
                        "description": "El procesamiento de tu documento fallo.",
                        "default_channels": ["inapp", "email"],
                        "available_channels": ["inapp", "email"],
                        "is_silenceable": True,
                    },
                ],
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request):
        return Response([event.to_public_dict() for event in iter_events()])
