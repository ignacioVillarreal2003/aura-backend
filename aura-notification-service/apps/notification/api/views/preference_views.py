from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notification.api.serializers import (
    EventPreferencesEntrySerializer,
    EventPreferenceUpdateSerializer,
    NotificationPreferenceSerializer,
    NotificationPreferenceUpdateSerializer,
)
from core.openapi.common import standard_error_responses
from apps.notification.events import get_event, is_known_event
from apps.notification.services import preference_service
from core.authorization import AccessControl
from core.authorization.permissions import (
    NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT,
    NOTIFICATION_PREFERENCES_EVENT_TYPES_GET,
    NOTIFICATION_PREFERENCES_GLOBAL_GET,
    NOTIFICATION_PREFERENCES_GLOBAL_PUT,
)
from core.exceptions.base import NotFoundException

_PREFS_EXAMPLE = {
    "user_id": 42,
    "inapp_enabled": True,
    "email_enabled": True,
    "mute_until": None,
    "updated_at": "2024-05-10T20:00:00Z",
}

_EVENT_ENTRY_EXAMPLE = {
    "event_type": "chat.member.invited",
    "type": "event",
    "severity": "info",
    "description": "Te invitaron a un chat.",
    "default_channels": ["inapp"],
    "available_channels": ["inapp", "email"],
    "is_silenceable": True,
    "channels": {"inapp": True, "email": False},
}


@extend_schema(tags=["Preferences"])
class GlobalPreferenceView(APIView):
    @extend_schema(
        summary="Leer preferencias globales del usuario",
        description=(
            "Devuelve las preferencias globales de notificación del usuario autenticado. "
            "Si el usuario nunca configuró preferencias, se devuelven los valores por defecto "
            "(in-app habilitado, email habilitado, sin mute, sin quiet hours).\n\n"
            "**Permiso requerido:** `NOTIFICATION_PREFERENCES_GLOBAL_GET`"
        ),
        responses={
            200: NotificationPreferenceSerializer,
            **standard_error_responses(401, 403),
        },
        examples=[
            OpenApiExample(
                "Respuesta exitosa",
                value=_PREFS_EXAMPLE,
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request):
        AccessControl.require_permissions(
            request.user, frozenset({NOTIFICATION_PREFERENCES_GLOBAL_GET})
        )
        prefs = preference_service.get_global(request.user.id)
        return Response(NotificationPreferenceSerializer(prefs).data)

    @extend_schema(
        summary="Actualizar preferencias globales del usuario",
        description=(
            "Actualiza las preferencias globales de notificación. Todos los campos son opcionales; "
            "solo se actualizan los enviados.\n\n"
            "**Reglas de validación:**\n"
            "- `mute_until` debe ser un datetime futuro. Enviar `null` para eliminar el mute activo.\n\n"
            "**Permiso requerido:** `NOTIFICATION_PREFERENCES_GLOBAL_PUT`"
        ),
        request=NotificationPreferenceUpdateSerializer,
        responses={
            200: NotificationPreferenceSerializer,
            **standard_error_responses(400, 401, 403),
        },
        examples=[
            OpenApiExample(
                "Deshabilitar email globalmente",
                value={"email_enabled": False},
                request_only=True,
            ),
            OpenApiExample(
                "Silenciar hasta una fecha",
                value={"mute_until": "2024-05-15T08:00:00Z"},
                request_only=True,
            ),
            OpenApiExample(
                "Eliminar mute activo",
                value={"mute_until": None},
                request_only=True,
            ),
            OpenApiExample(
                "Respuesta exitosa",
                value=_PREFS_EXAMPLE,
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "mute_until en el pasado",
                value={"error": "bad_request", "detail": "Validation failed", "status_code": 400, "fields": {"mute_until": ["mute_until must be a future datetime."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def put(self, request):
        AccessControl.require_permissions(
            request.user, frozenset({NOTIFICATION_PREFERENCES_GLOBAL_PUT})
        )
        serializer = NotificationPreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        prefs = preference_service.upsert_global(
            user_id=request.user.id,
            inapp_enabled=data.get("inapp_enabled"),
            email_enabled=data.get("email_enabled"),
            mute_until=data.get("mute_until") if data.get("mute_until") is not None else None,
            clear_mute=("mute_until" in data and data["mute_until"] is None),
            updated_by=request.user.id,
        )
        return Response(NotificationPreferenceSerializer(prefs).data)


@extend_schema(tags=["Preferences"])
class EventPreferenceListView(APIView):
    @extend_schema(
        summary="Listar preferencias por tipo de evento",
        description=(
            "Devuelve el catálogo completo de tipos de evento con el estado efectivo por canal "
            "para el usuario autenticado. Cada entrada combina los valores por defecto del evento "
            "con los overrides guardados por el usuario.\n\n"
            "El campo `channels` refleja si el usuario **recibirá** notificaciones por ese canal "
            "para ese evento, considerando sus overrides. No considera el estado global "
            "(`inapp_enabled`, `email_enabled`, `mute_until`).\n\n"
            "**Permiso requerido:** `NOTIFICATION_PREFERENCES_EVENT_TYPES_GET`"
        ),
        responses={
            200: EventPreferencesEntrySerializer(many=True),
            **standard_error_responses(401, 403),
        },
        examples=[
            OpenApiExample(
                "Respuesta exitosa",
                value=[
                    _EVENT_ENTRY_EXAMPLE,
                    {
                        "event_type": "auth.password.changed",
                        "type": "system",
                        "severity": "critical",
                        "description": "Cambio de contrasena exitoso.",
                        "default_channels": ["inapp", "email"],
                        "available_channels": ["inapp", "email"],
                        "is_silenceable": False,
                        "channels": {"inapp": True, "email": True},
                    },
                ],
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request):
        AccessControl.require_permissions(
            request.user, frozenset({NOTIFICATION_PREFERENCES_EVENT_TYPES_GET})
        )
        catalogue = preference_service.event_catalogue_for(request.user.id)
        return Response(catalogue)


@extend_schema(tags=["Preferences"])
class EventPreferenceDetailView(APIView):
    @extend_schema(
        summary="Actualizar preferencia para un tipo de evento",
        description=(
            "Guarda un override de canal para un tipo de evento específico del usuario autenticado. "
            "Al menos uno de `inapp_enabled` o `email_enabled` es requerido.\n\n"
            "El override persiste independientemente de los defaults del evento. "
            "Para restaurar los defaults, actualizar al valor por defecto del evento "
            "(consultable en `GET /api/v1/event-types/`).\n\n"
            "**Nota:** Los eventos con `is_silenceable: false` (como `auth.password.changed`) "
            "ignoran estos overrides al momento del despacho.\n\n"
            "**Permiso requerido:** `NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT`"
        ),
        request=EventPreferenceUpdateSerializer,
        responses={
            200: EventPreferencesEntrySerializer,
            **standard_error_responses(400, 401, 403, 404),
        },
        examples=[
            OpenApiExample(
                "Deshabilitar email para un evento",
                value={"email_enabled": False},
                request_only=True,
            ),
            OpenApiExample(
                "Habilitar ambos canales",
                value={"inapp_enabled": True, "email_enabled": True},
                request_only=True,
            ),
            OpenApiExample(
                "Respuesta exitosa",
                value=_EVENT_ENTRY_EXAMPLE,
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Tipo de evento no encontrado",
                value={"error": "event_type_not_found", "detail": "Unknown event_type.", "status_code": 404},
                response_only=True,
                status_codes=["404"],
            ),
            OpenApiExample(
                "Ningún campo enviado",
                value={"error": "bad_request", "detail": "Validation failed", "status_code": 400, "fields": {"non_field_errors": ["At least one of inapp_enabled or email_enabled is required."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def put(self, request, event_type: str):
        AccessControl.require_permissions(
            request.user, frozenset({NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT})
        )
        if not is_known_event(event_type):
            raise NotFoundException("Unknown event_type.", error_code="event_type_not_found")
        event = get_event(event_type)

        serializer = EventPreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for channel, enabled in serializer.to_channel_pairs():
            preference_service.set_event_preference(
                user_id=request.user.id,
                event_type=event_type,
                channel=channel,
                enabled=enabled,
                updated_by=request.user.id,
            )

        overrides = preference_service.event_override_map(request.user.id)
        entry = event.to_public_dict()
        entry["channels"] = {
            channel: overrides.get(
                (event.event_type, channel),
                channel in event.default_channels,
            )
            for channel in event.available_channels
        }
        return Response(entry)
