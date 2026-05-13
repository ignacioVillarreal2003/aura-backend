import logging
from django.conf import settings as _settings
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import ExportTooLargeException, MessageAccessDeniedException, MessageNotFoundException
from apps.message.models.chat_message import ChatMessage
from apps.message.repositories.message_repository import message_repository
from apps.message.services.export_service import (
    generate_ai_responses_markdown,
    generate_chat_json,
    generate_chat_markdown,
    generate_chat_pdf,
    generate_message_pdf,
)
from core.authorization import AccessControl
from core.authorization.permissions import EXPORT_CHAT
from core.openapi.common import standard_error_responses

logger = logging.getLogger(__name__)

_MAX_EXPORT_MESSAGES: int = getattr(_settings, "EXPORT_MAX_MESSAGES", 2_000)


def _get_chat_or_raise(chat_id: int, user_id: int):
    chat = chat_repository.get_by_id(chat_id)
    if chat is None:
        raise ChatNotFoundException()
    if not membership_repository.is_active_member(chat_id, user_id):
        raise MessageAccessDeniedException()
    return chat


def _load_messages(chat_id: int) -> list[ChatMessage]:
    qs = message_repository.get_messages_by_chat(chat_id).order_by("created_at")
    messages = list(qs[: _MAX_EXPORT_MESSAGES + 1])
    if len(messages) > _MAX_EXPORT_MESSAGES:
        raise ExportTooLargeException()
    return messages


class ChatExportPDFView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export full chat as PDF",
        operation_id="v1_chats_messages_export_pdf_chat",
        description=(
            "Downloads the **full** conversation as a PDF attachment. Requires chat membership and `EXPORT_CHAT`."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: OpenApiResponse(description="PDF binary — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 413),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({EXPORT_CHAT}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = _load_messages(chat_id)
        pdf = generate_chat_pdf(chat, messages)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}.pdf"'
        return response


class ChatExportMarkdownView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export full chat as Markdown",
        description="Downloads the **full** chat transcript as Markdown (`Content-Disposition: attachment`).",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: OpenApiResponse(description="Markdown text — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404, 413),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({EXPORT_CHAT}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = _load_messages(chat_id)
        content = generate_chat_markdown(chat, messages)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}.md"'
        return response


class ChatExportJSONView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export full chat as JSON",
        description="Structured **backup** of chat metadata and messages as downloadable JSON.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: OpenApiResponse(description="JSON backup — Content-Type: application/json"),
            **standard_error_responses(401, 403, 404, 413),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({EXPORT_CHAT}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = _load_messages(chat_id)
        content = generate_chat_json(chat, messages)
        response = HttpResponse(content, content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}.json"'
        return response


class AIResponsesExportView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export AI responses only as Markdown",
        description="Like full Markdown export but **only assistant/system** messages, for summaries or QA excerpts.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: OpenApiResponse(description="Markdown text — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404, 413),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({EXPORT_CHAT}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = _load_messages(chat_id)
        content = generate_ai_responses_markdown(chat, messages)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}_ai.md"'
        return response


class MessageExportPDFView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export single message as PDF",
        operation_id="v1_chats_messages_export_pdf_message",
        description="Renders **one** message (with chat context as implemented by the generator) as a PDF attachment.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="message_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: OpenApiResponse(description="PDF binary — Content-Type: application/pdf"),
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
