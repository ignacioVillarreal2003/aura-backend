import logging
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.dateparse import parse_datetime

from apps.notification.api.serializers import (
    BulkMarkReadResponseSerializer,
    MarkAllReadRequestSerializer,
    NotificationSerializer,
    NotificationStatusUpdateSerializer,
    UnreadCountSerializer,
)
from apps.notification.services import notification_service
from core.authorization import AccessControl
from core.authorization.permissions import (
    NOTIFICATION_DETAIL_GET,
    NOTIFICATION_INBOX_LIST,
    NOTIFICATION_MARK_ALL_READ_POST,
    NOTIFICATION_SOFT_DELETE,
    NOTIFICATION_STATUS_PATCH,
    NOTIFICATION_UNREAD_COUNT_GET,
)
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_NOTIFICATION_EXAMPLE = {
    "id": 123,
    "receiver_id": 42,
    "event_type": "chat.member.invited",
    "message": "Te invitaron al chat Proyecto X",
    "data": {"chat_id": 15, "chat_name": "Proyecto X"},
    "severity": "info",
    "link_url": "https://app.ejemplo.com/chats/15",
    "actor_name": "otro.usuario",
    "status": "unread",
    "read_at": None,
    "created_by": 7,
    "created_at": "2024-05-10T14:23:00Z",
}


@extend_schema(tags=["Notifications"])
class NotificationListView(APIView):
    @extend_schema(
        summary="Listar notificaciones",
        description=(
            "Devuelve la bandeja de notificaciones paginada del usuario autenticado. "
            "Las notificaciones con soft-delete no se incluyen. "
            "Los resultados se ordenan por `created_at` descendente.\n\n"
            "**Permiso requerido:** `NOTIFICATION_INBOX_LIST`"
        ),
        parameters=[
            OpenApiParameter(
                "status",
                OpenApiTypes.STR,
                description=(
                    "Filtra por estado. Repetible para múltiples valores: `?status=unread&status=read`. "
                    "Valores: `unread`, `read`."
                ),
                many=True,
            ),
            OpenApiParameter(
                "event_type",
                OpenApiTypes.STR,
                description="Filtra por tipo de evento exacto (p. ej. `chat.member.invited`).",
            ),
            OpenApiParameter(
                "since",
                OpenApiTypes.DATETIME,
                description=(
                    "Solo devuelve notificaciones con `created_at >= valor`. "
                    "Formato ISO 8601 (p. ej. `2024-01-15T10:30:00Z`)."
                ),
            ),
            OpenApiParameter(
                "page",
                OpenApiTypes.INT,
                description="Número de página (base 1).",
            ),
            OpenApiParameter(
                "page_size",
                OpenApiTypes.INT,
                description="Resultados por página. Por defecto 20, máximo 100.",
            ),
        ],
        responses={
            200: NotificationSerializer(many=True),
            **standard_error_responses(400, 401, 403),
        },
        examples=[
            OpenApiExample(
                "Respuesta exitosa",
                value={
                    "count": 47,
                    "next": "/api/v1/notifications/?page=2",
                    "previous": None,
                    "results": [_NOTIFICATION_EXAMPLE],
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Parámetro since inválido",
                value={"detail": "Invalid 'since' format. Use ISO 8601 (e.g. 2024-01-15T10:30:00Z).", "error": "invalid_since"},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def get(self, request):
        user = request.user
        AccessControl.require_permissions(user, frozenset({NOTIFICATION_INBOX_LIST}))

        status_filter = request.query_params.getlist("status") or None
        event_type = request.query_params.get("event_type")

        since = None
        since_str = request.query_params.get("since")
        if since_str:
            since = parse_datetime(since_str)
            if since is None:
                return Response(
                    {"detail": "Invalid 'since' format. Use ISO 8601 (e.g. 2024-01-15T10:30:00Z).", "error": "invalid_since"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        queryset = notification_service.list_for_user(
            user.id,
            status_in=status_filter,
            event_type=event_type,
            since=since,
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(tags=["Notifications"])
class NotificationUnreadCountView(APIView):
    @extend_schema(
        summary="Cantidad de notificaciones no leídas",
        description=(
            "Devuelve el total de notificaciones con estado `unread` del usuario autenticado. "
            "Útil para mostrar un badge en la UI sin cargar la bandeja completa.\n\n"
            "**Permiso requerido:** `NOTIFICATION_UNREAD_COUNT_GET`"
        ),
        responses={
            200: UnreadCountSerializer,
            **standard_error_responses(401, 403),
        },
        examples=[
            OpenApiExample(
                "Respuesta exitosa",
                value={"count": 5},
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    def get(self, request):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_UNREAD_COUNT_GET}))
        count = notification_service.unread_count(request.user.id)
        return Response({"count": count})


@extend_schema(tags=["Notifications"])
class NotificationDetailView(APIView):
    @extend_schema(
        summary="Detalle de una notificación",
        description=(
            "Devuelve el detalle de una notificación perteneciente al usuario autenticado. "
            "Devuelve 404 si la notificación no existe, fue eliminada con soft-delete, "
            "o pertenece a otro usuario.\n\n"
            "**Permiso requerido:** `NOTIFICATION_DETAIL_GET`"
        ),
        responses={
            200: NotificationSerializer,
            **standard_error_responses(401, 403, 404),
        },
        examples=[
            OpenApiExample(
                "Respuesta exitosa",
                value=_NOTIFICATION_EXAMPLE,
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Notificación no encontrada",
                value={"error": "notification_not_found", "detail": "Notification not found.", "status_code": 404},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    def get(self, request, pk: int):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_DETAIL_GET}))
        notification = notification_service.get_for_user(request.user.id, pk)
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        summary="Cambiar estado de una notificación",
        description=(
            "Actualiza el estado de una notificación del usuario autenticado. "
            "Tras el cambio, se publica un evento en tiempo real por SSE "
            "(`notification.updated`) con el nuevo estado.\n\n"
            "**Permiso requerido:** `NOTIFICATION_STATUS_PATCH`"
        ),
        request=NotificationStatusUpdateSerializer,
        responses={
            200: NotificationSerializer,
            **standard_error_responses(400, 401, 403, 404),
        },
        examples=[
            OpenApiExample(
                "Marcar como leída",
                value={"status": "read"},
                request_only=True,
            ),
            OpenApiExample(
                "Marcar como no leída",
                value={"status": "unread"},
                request_only=True,
            ),
            OpenApiExample(
                "Respuesta exitosa",
                value={**_NOTIFICATION_EXAMPLE, "status": "read", "read_at": "2024-05-10T15:00:00Z"},
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Estado inválido",
                value={"error": "bad_request", "detail": "Validation failed", "status_code": 400, "fields": {"status": ["\"invalido\" is not a valid choice."]}},
                response_only=True,
                status_codes=["400"],
            ),
        ],
    )
    def patch(self, request, pk: int):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_STATUS_PATCH}))
        serializer = NotificationStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification = notification_service.update_status(
            request.user.id, pk, serializer.validated_data["status"]
        )
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        summary="Borrar notificación (soft-delete)",
        description=(
            "Marca la notificación como eliminada (`deleted_at = now()`). "
            "La fila permanece en la base de datos pero deja de aparecer en todos los endpoints del usuario. "
            "Se publica un evento SSE `notification.deleted` con el `id` eliminado.\n\n"
            "**Permiso requerido:** `NOTIFICATION_SOFT_DELETE`"
        ),
        responses={
            204: None,
            **standard_error_responses(401, 403, 404),
        },
        examples=[
            OpenApiExample(
                "Notificación no encontrada",
                value={"error": "notification_not_found", "detail": "Notification not found.", "status_code": 404},
                response_only=True,
                status_codes=["404"],
            ),
        ],
    )
    def delete(self, request, pk: int):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_SOFT_DELETE}))
        notification_service.soft_delete(request.user.id, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Notifications"])
class MarkAllReadView(APIView):
    @extend_schema(
        summary="Marcar todas las notificaciones como leídas",
        description=(
            "Marca como leídas todas las notificaciones con estado `unread` del usuario autenticado. "
            "Si se envía `until_id`, solo se marcan las notificaciones con `id <= until_id`. "
            "Se publica un evento SSE `notification.updated` con el resumen del bulk update.\n\n"
            "**Permiso requerido:** `NOTIFICATION_MARK_ALL_READ_POST`"
        ),
        request=MarkAllReadRequestSerializer,
        responses={
            200: BulkMarkReadResponseSerializer,
            **standard_error_responses(401, 403),
        },
        examples=[
            OpenApiExample(
                "Marcar todas",
                value={},
                request_only=True,
                description="Cuerpo vacío: marca todas las no leídas.",
            ),
            OpenApiExample(
                "Marcar hasta un ID específico",
                value={"until_id": 200},
                request_only=True,
                description="Solo marca como leídas las notificaciones con id <= 200.",
            ),
            OpenApiExample(
                "Respuesta exitosa",
                value={"updated": 12},
                response_only=True,
                status_codes=["200"],
                description="12 notificaciones fueron marcadas como leídas.",
            ),
        ],
    )
    def post(self, request):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_MARK_ALL_READ_POST}))
        serializer = MarkAllReadRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        updated = notification_service.mark_all_read(
            request.user.id,
            until_id=serializer.validated_data.get("until_id"),
        )
        return Response({"updated": updated})

