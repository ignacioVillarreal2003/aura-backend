import logging
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact.audio import transcribe as _transcribe
from apps.artifact_message.exceptions import (
    ChatAiReplyInProgressException,
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
    RegenerateResponseSerializer,
    SendMessagePostResponseSerializer,
    SendMessageRequest,
)
from apps.artifact_message.services.export_service import (
    generate_message_markdown,
    generate_message_pdf,
)
from apps.artifact_message.services.message_service import (
    ChatAIMode,
    broadcast_chat_ai_lock_change,
    message_service,
)
from apps.chat.ai_reply_lock import release, try_acquire
from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.chat.ws_rate_limit import check_message_rate_limit
from apps.membership.repositories.membership_repository import membership_repository
from core.authorization import AccessControl
from core.authorization.permissions import EXPORT_CHAT, MANAGE_CHATS
from core.openapi.common import standard_error_responses
from core.pagination.pagination import MessageCursorPagination

logger = logging.getLogger(__name__)

_CHAT_ID_PATH_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
)
_MESSAGE_ID_PATH_PARAM = OpenApiParameter(
    name="message_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del mensaje (`ArtifactMessage.id`, campo `id` en el listado).",
)


def _get_chat_or_raise(chat_id: int, user_id: int):
    chat = chat_repository.get_by_id(chat_id)
    if chat is None:
        raise ChatNotFoundException()
    if not membership_repository.is_active_member(chat_id, user_id):
        raise MessageAccessDeniedException()
    return chat


class MessageListView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Listar mensajes",
        description=(
            "Devuelve el historial de mensajes del chat con **paginación por cursor** (más recientes primero). "
            "Cada ítem puede incluir anotaciones del usuario: `is_bookmarked`, `user_feedback` (1/-1 o null) "
            "y `thread_reply_count`."
        ),
        parameters=[_CHAT_ID_PATH_PARAM],
        responses={200: MessageResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
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
        parameters=[_CHAT_ID_PATH_PARAM],
        request={"multipart/form-data": SendMessageRequest, "application/json": SendMessageRequest},
        responses={
            201: SendMessagePostResponseSerializer,
            **standard_error_responses(400, 401, 403, 404, 409, 502, 503),
        },
    )
    def post(self, request: Request, chat_id: int) -> Response:
        return async_to_sync(self._post_async)(request, chat_id)

    async def _post_async(self, request: Request, chat_id: int) -> Response:
        serializer = SendMessageRequest(data=request.data)
        serializer.is_valid(raise_exception=True)

        mode = serializer.validated_data.get("mode", "document_question")

        # Verify membership before acquiring any lock so we never block the chat
        # for users who aren't members or when the chat doesn't exist.
        chat_obj = await sync_to_async(_get_chat_or_raise)(chat_id, request.user.id)
        is_ephemeral = chat_obj.is_ephemeral

        # Shared rate limit (same key as WebSocket) so both channels count together.
        if not await sync_to_async(check_message_rate_limit)(request.user.id, chat_id):
            return Response(
                {"detail": "Too many messages. Please wait before sending more.", "error": "rate_limit_exceeded"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        transcript = None
        if "audio" in serializer.validated_data:
            transcript = await sync_to_async(_transcribe)(serializer.validated_data["audio"])
            text = transcript
        else:
            text = serializer.validated_data["message"]

        if not await sync_to_async(try_acquire)(chat_id):
            raise ChatAiReplyInProgressException()

        await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, True)
        assistant = None
        assistant_error = None
        msg_data = None
        try:
            if is_ephemeral:
                # Ephemeral chats: validate access but do not persist messages.
                await sync_to_async(message_service.assert_send_access)(request.user, chat_id)
                msg_data = {
                    "id": None,
                    "artifact_id": None,
                    "chat_id": chat_id,
                    "message": text,
                    "sender_type": ArtifactMessage.SenderType.USER,
                    "created_by": request.user.id,
                    "created_at": None,
                    "is_bookmarked": False,
                    "user_feedback": None,
                    "user_feedback_reason": None,
                    "user_feedback_comment": None,
                    "thread_reply_count": 0,
                    "fragments": None,
                }
                try:
                    turn = await message_service.run_ephemeral_ai_reply(
                        mode, request.user, chat_id, text
                    )
                    assistant = {"question": turn.question, "answer": turn.answer, "fragments": turn.fragments}
                except LLMServiceException as e:
                    assistant_error = {"detail": e.detail}
                except Exception:
                    logger.exception(
                        "Unexpected error running ephemeral AI reply.",
                        extra={"chat_id": chat_id, "user_id": request.user.id, "mode": mode},
                    )
                    assistant_error = {"detail": "AI service encountered an unexpected error."}
            else:
                msg = await sync_to_async(message_service.send_message)(
                    user=request.user,
                    chat_id=chat_id,
                    text=text,
                )
                msg_data = MessageResponse(msg).data
                try:
                    turn = await message_service.run_ai_reply(mode, request.user, chat_id)
                    assistant = {"question": turn.question, "answer": turn.answer, "fragments": turn.fragments}
                except LLMServiceException as e:
                    assistant_error = {"detail": e.detail}
                except Exception:
                    logger.exception(
                        "Unexpected error running AI reply.",
                        extra={"chat_id": chat_id, "user_id": request.user.id, "mode": mode},
                    )
                    assistant_error = {"detail": "AI service encountered an unexpected error."}
        finally:
            await sync_to_async(release)(chat_id)
            await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, False)

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
        description="Devuelve el historial completo del chat sin requerir membresía activa. Requiere `MANAGE_CHATS`.",
        parameters=[_CHAT_ID_PATH_PARAM],
        responses={200: MessageResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        messages = message_service.get_messages_admin(user=request.user, chat_id=chat_id)
        paginator = MessageCursorPagination()
        page = paginator.paginate_queryset(messages, request)
        return paginator.get_paginated_response(MessageResponse(page, many=True).data)


class MessageManageExportPDFView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Exportar mensaje como PDF (admin)",
        description="Descarga cualquier mensaje como PDF sin requerir membresía. Requiere `MANAGE_CHATS`.",
        parameters=[_CHAT_ID_PATH_PARAM, _MESSAGE_ID_PATH_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, chat_id: int, message_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({MANAGE_CHATS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        message = message_repository.get_by_id_and_chat(message_id, chat_id)
        if message is None:
            raise MessageNotFoundException()
        pdf = generate_message_pdf(chat, message)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="message_{message_id}.pdf"'
        return response


class MessageManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Exportar mensaje como Markdown (admin)",
        description="Descarga cualquier mensaje como Markdown sin requerir membresía. Requiere `MANAGE_CHATS`.",
        parameters=[_CHAT_ID_PATH_PARAM, _MESSAGE_ID_PATH_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, chat_id: int, message_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({MANAGE_CHATS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        message = message_repository.get_by_id_and_chat(message_id, chat_id)
        if message is None:
            raise MessageNotFoundException()
        content = generate_message_markdown(chat, message)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="message_{message_id}.md"'
        return response


class MessageRegenerateView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Regenerar última respuesta IA",
        description=(
            "Elimina el último mensaje del asistente y ejecuta el flujo IA nuevamente con el mismo contexto. "
            "Acepta un campo `mode` opcional. Retorna **409** si ya hay una respuesta IA en curso."
        ),
        request=None,
        parameters=[_CHAT_ID_PATH_PARAM],
        responses={
            200: RegenerateResponseSerializer,
            **standard_error_responses(401, 403, 404, 409, 502, 503),
        },
    )
    def post(self, request: Request, chat_id: int) -> Response:
        return async_to_sync(self._post_async)(request, chat_id)

    async def _post_async(self, request: Request, chat_id: int) -> Response:
        mode = ChatAIMode.normalize(
            request.data.get("mode") if isinstance(request.data, dict) else None
        )

        if not await sync_to_async(try_acquire)(chat_id):
            raise ChatAiReplyInProgressException()

        await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, True)
        assistant = None
        assistant_error = None
        try:
            regen_feedback = await sync_to_async(message_service.delete_last_ai_message)(
                request.user, chat_id
            )
            try:
                turn = await message_service.run_ai_reply(
                    mode, request.user, chat_id, regen_feedback=regen_feedback
                )
                assistant = {"question": turn.question, "answer": turn.answer, "fragments": turn.fragments}
            except LLMServiceException as e:
                assistant_error = {"detail": e.detail}
            except Exception:
                logger.exception(
                    "Unexpected error regenerating AI response.",
                    extra={"chat_id": chat_id, "user_id": request.user.id},
                )
                assistant_error = {"detail": "AI service encountered an unexpected error."}
        finally:
            await sync_to_async(release)(chat_id)
            await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, False)

        return Response(
            {"assistant": assistant, "assistant_error": assistant_error},
            status=status.HTTP_200_OK,
        )


class MessageDetailView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Eliminar mensaje",
        description="Elimina suavemente un mensaje. Solo el dueño del chat puede eliminar mensajes.",
        parameters=[_CHAT_ID_PATH_PARAM, _MESSAGE_ID_PATH_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, chat_id: int, message_id: int) -> Response:
        message_service.delete_message(
            user=request.user,
            chat_id=chat_id,
            message_id=message_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageExportPDFView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Exportar mensaje como PDF",
        operation_id="v1_chats_messages_export_pdf_message",
        description="Descarga un mensaje como PDF. Requiere membresía activa y `EXPORT_CHAT`.",
        parameters=[_CHAT_ID_PATH_PARAM, _MESSAGE_ID_PATH_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, chat_id: int, message_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({EXPORT_CHAT}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        message = message_repository.get_by_id_and_chat(message_id, chat_id)
        if message is None:
            raise MessageNotFoundException()
        pdf = generate_message_pdf(chat, message)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="message_{message_id}.pdf"'
        return response


class MessageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Messages"],
        summary="Exportar mensaje como Markdown",
        description="Descarga un mensaje como Markdown. Requiere membresía activa y `EXPORT_CHAT`.",
        parameters=[_CHAT_ID_PATH_PARAM, _MESSAGE_ID_PATH_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, chat_id: int, message_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({EXPORT_CHAT}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        message = message_repository.get_by_id_and_chat(message_id, chat_id)
        if message is None:
            raise MessageNotFoundException()
        content = generate_message_markdown(chat, message)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="message_{message_id}.md"'
        return response
