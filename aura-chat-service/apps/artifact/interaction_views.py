import logging
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact.interaction_serializers import (
    ArtifactPinResponse,
    FeedbackAnalyticsResponse,
    FeedbackResponse,
    SendThreadReplyRequest,
    SetFeedbackRequest,
    ThreadReplyResponse,
    UpdateThreadReplyRequest,
)
from apps.artifact.serializers import ArtifactSummaryResponse, PinnedArtifactResponse
from apps.artifact.services.artifact_bookmark_service import bookmark_service
from apps.artifact.services.artifact_feedback_service import feedback_service
from apps.artifact.services.artifact_pin_service import pin_service
from apps.artifact.services.artifact_thread_service import thread_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_ID_PARAM = [
    OpenApiParameter(name="artifact_id", type=int, location=OpenApiParameter.PATH, required=True),
]
_CHAT_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=True,
    description="Chat de origen. El usuario debe ser miembro activo.",
)


def _required_chat_id(request: Request) -> int:
    raw = request.query_params.get("chat_id")
    if raw is None or not raw.isdigit():
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"chat_id": "Se requiere un chat_id válido."})
    return int(raw)


class ArtifactFeedbackView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Enviar feedback de un artefacto",
        description=(
                "Crea o actualiza el feedback **pulgar arriba (1) / pulgar abajo (-1)** sobre un artefacto de "
                "tipo MESSAGE generado por el asistente. Devuelve **400** si el artefacto no es una respuesta de IA."
        ),
        parameters=_ID_PARAM,
        request=SetFeedbackRequest,
        responses={200: FeedbackResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request, artifact_id: int) -> Response:
        serializer = SetFeedbackRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        fb = feedback_service.set_feedback(
            user=request.user,
            artifact_id=artifact_id,
            value=data["value"],
            reason=data.get("reason"),
            comment=data.get("comment"),
        )
        return Response(FeedbackResponse(fb).data)

    @extend_schema(
        tags=["Artifacts"],
        summary="Eliminar feedback",
        description="Elimina el pulgar arriba/abajo del usuario autenticado sobre este artefacto (si existe).",
        parameters=_ID_PARAM,
        responses={204: OpenApiResponse(description="Sin contenido"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, artifact_id: int) -> Response:
        feedback_service.delete_feedback(user=request.user, artifact_id=artifact_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArtifactBookmarkView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Marcar artefacto",
        description="Agrega un **marcador personal** sobre este artefacto para el usuario autenticado.",
        request=None,
        parameters=_ID_PARAM,
        responses={204: OpenApiResponse(description="Sin contenido"), **standard_error_responses(401, 403, 404)},
    )
    def post(self, request: Request, artifact_id: int) -> Response:
        bookmark_service.bookmark(user=request.user, artifact_id=artifact_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Artifacts"],
        summary="Quitar marcador",
        description="Elimina el marcador del usuario sobre este artefacto (si existe).",
        request=None,
        parameters=_ID_PARAM,
        responses={204: OpenApiResponse(description="Sin contenido"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, artifact_id: int) -> Response:
        bookmark_service.unbookmark(user=request.user, artifact_id=artifact_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArtifactPinView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Fijar un artefacto",
        description="Fija el artefacto para que aparezca en la lista de fijados del chat (owner del chat).",
        parameters=_ID_PARAM,
        request=None,
        responses={201: ArtifactPinResponse, **standard_error_responses(401, 403, 404)},
    )
    def post(self, request: Request, artifact_id: int) -> Response:
        pin = pin_service.pin(user=request.user, artifact_id=artifact_id)
        return Response(ArtifactPinResponse(pin).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Artifacts"],
        summary="Desfijar un artefacto",
        description="Quita el fijado del artefacto en el chat (idempotente).",
        parameters=_ID_PARAM,
        responses={204: OpenApiResponse(description="Sin contenido"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, artifact_id: int) -> Response:
        pin_service.unpin(user=request.user, artifact_id=artifact_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArtifactThreadView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Listar respuestas del hilo",
        description="Devuelve las respuestas del hilo del artefacto en orden cronológico, paginadas.",
        parameters=_ID_PARAM,
        responses={200: ThreadReplyResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, artifact_id: int) -> Response:
        replies = thread_service.get_thread(user=request.user, artifact_id=artifact_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(replies, request)
        return paginator.get_paginated_response(ThreadReplyResponse(page, many=True).data)

    @extend_schema(
        tags=["Artifacts"],
        summary="Agregar respuesta al hilo",
        description="Crea una respuesta de hilo sobre el artefacto, para discusiones laterales.",
        parameters=_ID_PARAM,
        request=SendThreadReplyRequest,
        responses={201: ThreadReplyResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request, artifact_id: int) -> Response:
        serializer = SendThreadReplyRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = thread_service.add_reply(
            user=request.user,
            artifact_id=artifact_id,
            message_text=serializer.validated_data["message"],
        )
        return Response(ThreadReplyResponse(reply).data, status=status.HTTP_201_CREATED)


_REPLY_ID_PARAM = [
    *_ID_PARAM,
    OpenApiParameter(name="reply_id", type=int, location=OpenApiParameter.PATH, required=True),
]


class ArtifactThreadReplyDetailView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Editar respuesta del hilo",
        description="Actualiza el texto de una respuesta del hilo. Solo el autor puede editar su propia respuesta.",
        parameters=_REPLY_ID_PARAM,
        request=UpdateThreadReplyRequest,
        responses={200: ThreadReplyResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def patch(self, request: Request, artifact_id: int, reply_id: int) -> Response:
        serializer = UpdateThreadReplyRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = thread_service.update_reply(
            user=request.user,
            artifact_id=artifact_id,
            reply_id=reply_id,
            message_text=serializer.validated_data["message"],
        )
        return Response(ThreadReplyResponse(reply).data)

    @extend_schema(
        tags=["Artifacts"],
        summary="Eliminar respuesta del hilo",
        description="Elimina una respuesta del hilo. Solo el autor puede eliminar su propia respuesta.",
        parameters=_REPLY_ID_PARAM,
        responses={204: OpenApiResponse(description="Sin contenido"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, artifact_id: int, reply_id: int) -> Response:
        thread_service.delete_reply(user=request.user, artifact_id=artifact_id, reply_id=reply_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PinnedArtifactListView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Listar artefactos fijados en un chat",
        description="Lista los artefactos fijados en el chat (cualquier tipo), paginados.",
        parameters=[_CHAT_PARAM],
        responses={200: PinnedArtifactResponse(many=True), **standard_error_responses(400, 401, 403, 404)},
    )
    def get(self, request: Request) -> Response:
        chat_id = _required_chat_id(request)
        pins = pin_service.list_pinned(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(pins, request)
        return paginator.get_paginated_response(PinnedArtifactResponse(page, many=True).data)


class BookmarkedArtifactListView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Listar artefactos marcados en un chat",
        description="Lista los artefactos que el usuario marcó en el chat (cualquier tipo), paginados.",
        parameters=[_CHAT_PARAM],
        responses={200: ArtifactSummaryResponse(many=True), **standard_error_responses(400, 401, 403, 404)},
    )
    def get(self, request: Request) -> Response:
        chat_id = _required_chat_id(request)
        artifacts = bookmark_service.list_bookmarked(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(artifacts, request)
        return paginator.get_paginated_response(ArtifactSummaryResponse(page, many=True, context={'request': request}).data)


class FeedbackAnalyticsView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Dashboard de analytics de feedback (admin)",
        description=(
                "Satisfacción agregada pulgar arriba/abajo en una ventana deslizante: resumen global, "
                "desglose por asistente (peores primero), desglose por motivo y entradas negativas recientes. "
                "Requiere permiso `VIEW_FEEDBACK_ANALYTICS`."
        ),
        parameters=[
            OpenApiParameter(
                name="days",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Ventana en días (default 30, máximo 3650).",
            ),
            OpenApiParameter(
                name="chat_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filtrar por chat de origen.",
            ),
            OpenApiParameter(
                name="artifact_type",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filtrar por tipo de artefacto.",
            ),
            OpenApiParameter(
                name="user_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filtrar por ID del usuario que envió el feedback.",
            ),
            OpenApiParameter(
                name="reason",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filtrar por código de motivo de feedback negativo.",
            ),
        ],
        responses={200: FeedbackAnalyticsResponse, **standard_error_responses(401, 403)},
    )
    def get(self, request: Request) -> Response:
        from apps.artifact.services.artifact_feedback_analytics_service import feedback_analytics_service

        def _int_param(name: str) -> int | None:
            raw = request.query_params.get(name)
            if raw is not None:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    pass
            return None

        days = _int_param("days")
        chat_id = _int_param("chat_id")
        user_id = _int_param("user_id")
        artifact_type = request.query_params.get("artifact_type") or None
        reason = request.query_params.get("reason") or None

        data = feedback_analytics_service.get_analytics(
            user=request.user,
            days=days,
            chat_id=chat_id,
            artifact_type=artifact_type,
            user_id=user_id,
            reason=reason,
        )
        return Response(FeedbackAnalyticsResponse(data).data)
