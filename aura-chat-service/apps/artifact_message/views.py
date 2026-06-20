import logging
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact.audio import transcribe as _transcribe
from apps.artifact_message.exceptions import (
    LLMServiceException,
    MessageAccessDeniedException,
    MessageNotFoundException,
)
from apps.artifact_message.models import ArtifactMessage
from apps.artifact_message.repositories.message_repository import message_repository
from apps.artifact_message.serializers import (
    AssistantBlockSerializer,
    AssistantErrorSerializer,
    MessageResponse,
    SendMessagePostResponseSerializer,
    SendMessageRequest,
)
from apps.artifact_message.services.message_service import (
    ChatAIMode,
    message_service,
)
from apps.chat.ai_lock_guard import ai_reply_lock_guard
from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.chat.ws_rate_limit import check_message_rate_limit, check_transcribe_rate_limit
from apps.membership.repositories.membership_repository import membership_repository
from core.authorization import AccessControl
from apps.artifact_message.services.export_service import (
    generate_message_markdown,
    generate_message_pdf,
)
from core.authorization.permissions import (
    EXPORT_MESSAGE,
    GET_MESSAGE,
    LIST_MESSAGES,
    MANAGE_EXPORT_MESSAGE,
)
from core.openapi.common import standard_error_responses
from core.pagination.pagination import MessageCursorPagination

logger = logging.getLogger(__name__)

_CHAT_ID_QUERY_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=True,
    description="ID del chat.",
)
_MESSAGE_ID_PATH_PARAM = OpenApiParameter(
    name="message_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del mensaje (`ArtifactMessage.id`, campo `id` en el listado).",
)


def _require_chat_id_param(request: Request) -> int:
    raw = request.query_params.get("chat_id")
    if not raw or not raw.isdigit():
        raise ValidationError({"chat_id": "Se requiere chat_id válido."})
    return int(raw)


def _get_chat_or_raise(chat_id: int, user_id: int):
    chat = chat_repository.get_by_id(chat_id)
    if chat is None:
        raise ChatNotFoundException()
    if not membership_repository.is_active_member(chat_id, user_id):
        raise MessageAccessDeniedException()
    return chat


def _get_message_or_raise(message_id: int) -> ArtifactMessage:
    msg = message_repository.get_by_id(message_id)
    if msg is None:
        raise MessageNotFoundException()
    return msg


class MessageListView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Listar mensajes",
        description=(
                "Devuelve el historial de mensajes del chat con **paginación por cursor** (más recientes primero). "
                "Cada ítem puede incluir anotaciones del usuario: `is_bookmarked`, `user_feedback` (1/-1 o null) "
                "y `thread_reply_count`."
        ),
        parameters=[_CHAT_ID_QUERY_PARAM],
        responses={200: MessageResponse(many=True), **standard_error_responses(400, 401, 403, 404)},
    )
    def get(self, request: Request) -> Response:
        chat_id = _require_chat_id_param(request)
        messages = message_service.get_messages(user=request.user, chat_id=chat_id)
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(messages, request)
        return paginator.get_paginated_response(MessageResponse(page, many=True).data)


class MessageGenerateView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Enviar mensaje",
        description=(
                "Envía **texto** (`message`) **o** un audio (`audio` multipart)—no ambos. "
                "El audio se transcribe en el servidor; el transcript aparece en `transcript` en la respuesta. "
                "Retorna **409** si ya hay una respuesta IA en curso para este chat."
        ),
        request={"multipart/form-data": SendMessageRequest, "application/json": SendMessageRequest},
        responses={
            201: SendMessagePostResponseSerializer,
            **standard_error_responses(400, 401, 403, 404, 409, 502, 503),
        },
    )
    def post(self, request: Request) -> Response:
        return async_to_sync(self._post_async)(request)

    async def _post_async(self, request: Request) -> Response:
        serializer = SendMessageRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        chat_id = serializer.validated_data["chat_id"]
        mode = serializer.validated_data.get("mode", "document_question")
        retrieve_context = serializer.validated_data.get("retrieve_context")
        process_documents = serializer.validated_data.get("process_documents")

        await sync_to_async(message_service.assert_send_access)(request.user, chat_id)

        if not await sync_to_async(check_message_rate_limit)(request.user.id, chat_id):
            return Response(
                {"detail": "Too many messages. Please wait before sending more.", "error": "rate_limit_exceeded"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        transcript = None
        if "audio" in serializer.validated_data:
            if not await sync_to_async(check_transcribe_rate_limit)(request.user.id):
                return Response(
                    {
                        "detail": "Too many transcription requests. Please wait.",
                        "error": "transcription_rate_limit_exceeded",
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            transcript = await sync_to_async(_transcribe)(serializer.validated_data["audio"])
            text = transcript
        else:
            text = serializer.validated_data["message"]

        assistant = None
        assistant_error = None
        msg_data = None
        async with ai_reply_lock_guard(chat_id):
            msg = await sync_to_async(message_service.send_message)(
                user=request.user,
                chat_id=chat_id,
                text=text,
            )
            msg_data = MessageResponse(msg).data
            try:
                turn = await message_service.run_ai_reply(
                    mode, request.user, chat_id,
                    retrieve_context=retrieve_context,
                    process_documents=process_documents,
                )
                assistant = {"question": turn.question, "answer": turn.answer, "fragments": turn.fragments}
            except LLMServiceException as e:
                assistant_error = {"detail": e.detail}
            except Exception:
                logger.exception(
                    "Unexpected error running AI reply.",
                    extra={"chat_id": chat_id, "user_id": request.user.id, "mode": mode},
                )
                assistant_error = {"detail": "AI service encountered an unexpected error."}

        return Response(
            {
                "message": msg_data,
                "transcript": transcript,
                "assistant": assistant,
                "assistant_error": assistant_error,
            },
            status=status.HTTP_201_CREATED,
        )


class MessageManageView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Listar mensajes (admin)",
        description="Devuelve el historial completo del chat sin requerir membresía activa. Requiere `MANAGE_MESSAGES`.",
        parameters=[_CHAT_ID_QUERY_PARAM],
        responses={200: MessageResponse(many=True), **standard_error_responses(400, 401, 403, 404)},
    )
    def get(self, request: Request) -> Response:
        chat_id = _require_chat_id_param(request)
        messages = message_service.get_messages_admin(user=request.user, chat_id=chat_id)
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(messages, request)
        return paginator.get_paginated_response(MessageResponse(page, many=True).data)


class MessageDetailView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Obtener mensaje",
        parameters=[_MESSAGE_ID_PATH_PARAM],
        responses={
            200: MessageResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, message_id: int) -> Response:
        AccessControl.require_permissions(request.user, frozenset({GET_MESSAGE}))
        plain = _get_message_or_raise(message_id)
        chat_id = plain.artifact.source_chat_id
        _get_chat_or_raise(chat_id, request.user.id)
        msg = message_repository.get_messages_by_chat(chat_id, user_id=request.user.id).filter(pk=message_id).first()
        if msg is None:
            raise MessageNotFoundException()
        return Response(MessageResponse(msg).data)

    @extend_schema(
        tags=["Messages"],
        summary="Eliminar mensaje",
        description="Elimina suavemente un mensaje. Solo el dueño del chat puede eliminar mensajes.",
        parameters=[_MESSAGE_ID_PATH_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, message_id: int) -> Response:
        msg = _get_message_or_raise(message_id)
        chat_id = msg.artifact.source_chat_id
        message_service.delete_message(user=request.user, chat_id=chat_id, message_id=message_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageExportPDFView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Exportar mensaje como PDF",
        parameters=[_MESSAGE_ID_PATH_PARAM],
        responses={200: OpenApiResponse(description="PDF"), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, message_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({EXPORT_MESSAGE}))
        msg = _get_message_or_raise(message_id)
        chat = _get_chat_or_raise(msg.artifact.source_chat_id, request.user.id)
        pdf = generate_message_pdf(chat, msg)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="message_{message_id}.pdf"'
        return response


class MessageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Exportar mensaje como Markdown",
        parameters=[_MESSAGE_ID_PATH_PARAM],
        responses={200: OpenApiResponse(description="Markdown"), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, message_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({EXPORT_MESSAGE}))
        msg = _get_message_or_raise(message_id)
        chat = _get_chat_or_raise(msg.artifact.source_chat_id, request.user.id)
        content = generate_message_markdown(chat, msg)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="message_{message_id}.md"'
        return response


class MessageManageExportPDFView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Exportar mensaje como PDF (admin)",
        parameters=[_MESSAGE_ID_PATH_PARAM],
        responses={200: OpenApiResponse(description="PDF"), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, message_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({MANAGE_EXPORT_MESSAGE}))
        msg = _get_message_or_raise(message_id)
        chat = chat_repository.get_by_id(msg.artifact.source_chat_id)
        if chat is None:
            raise ChatNotFoundException()
        pdf = generate_message_pdf(chat, msg)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="message_{message_id}.pdf"'
        return response


class MessageManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Exportar mensaje como Markdown (admin)",
        parameters=[_MESSAGE_ID_PATH_PARAM],
        responses={200: OpenApiResponse(description="Markdown"), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, message_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({MANAGE_EXPORT_MESSAGE}))
        msg = _get_message_or_raise(message_id)
        chat = chat_repository.get_by_id(msg.artifact.source_chat_id)
        if chat is None:
            raise ChatNotFoundException()
        content = generate_message_markdown(chat, msg)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="message_{message_id}.md"'
        return response
