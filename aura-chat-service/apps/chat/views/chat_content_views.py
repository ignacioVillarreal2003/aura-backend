import logging
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.services.chat_service import chat_service
from core.openapi.common import standard_error_responses

logger = logging.getLogger(__name__)

_CHAT_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
)


class ClearChatContentView(APIView):
    @extend_schema(
        tags=["Chats"],
        summary="Limpiar contenido del chat",
        description=(
                "Elimina suavemente **todos los artefactos** del chat (mensajes, informes, checklists, "
                "quizzes, líneas de tiempo, lecciones aprendidas, briefs de decisión, resúmenes y "
                "acciones de documentos). "
                "Solo el propietario del chat puede ejecutar esta acción."
        ),
        parameters=[_CHAT_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, chat_id: int) -> Response:
        chat_service.clear_content(user=request.user, chat_id=chat_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MarkChatAsReadView(APIView):
    @extend_schema(
        tags=["Chats"],
        summary="Marcar chat como leído",
        description=(
                "Actualiza la posición de **último leído** del usuario en el chat (membresía). "
                "Llamar cuando el usuario abre o desplaza hasta los mensajes más recientes."
        ),
        parameters=[_CHAT_PARAM],
        request=None,
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def post(self, request: Request, chat_id: int) -> Response:
        chat_service.mark_as_read(user=request.user, chat_id=chat_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
