from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notification.api.serializers import (
    NotificationPreferenceSerializer,
    NotificationPreferenceUpdateSerializer,
)
from core.openapi.common import standard_error_responses
from apps.notification.services import preference_service
from core.authorization import AccessControl
from core.authorization.permissions import (
    NOTIFICATION_PREFERENCES_GLOBAL_GET,
    NOTIFICATION_PREFERENCES_GLOBAL_PUT,
)

_PREFS_EXAMPLE = {
    "user_id": 42,
    "inapp_enabled": True,
    "email_enabled": True,
    "mute_until": None,
    "updated_at": "2024-05-10T20:00:00Z",
}


@extend_schema(tags=["Preferences"])
class GlobalPreferenceView(APIView):
    @extend_schema(
        summary="Leer preferencias globales del usuario",
        description=(
            "Devuelve las preferencias globales de notificación del usuario autenticado. "
            "Si el usuario nunca configuró preferencias, se devuelven los valores por defecto "
            "(in-app habilitado, email habilitado, sin mute).\n\n"
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
        )
        return Response(NotificationPreferenceSerializer(prefs).data)
