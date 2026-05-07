import logging

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from apps.message.exceptions import MessageAccessDeniedException, MessageNotFoundException
from apps.message.repositories.message_repository import message_repository
from apps.message.services.export_service import (
    generate_ai_responses_markdown,
    generate_chat_json,
    generate_chat_markdown,
    generate_chat_pdf,
    generate_message_pdf,
)
from core.authorization import AccessControl
from core.authorization.permissions import LIST_MESSAGES
from core.openapi.common import standard_error_responses

logger = logging.getLogger(__name__)


def _get_chat_or_raise(chat_id: int, user_id: int):
    chat = chat_repository.get_by_id(chat_id)
    if chat is None:
        raise ChatNotFoundException()
    if not membership_repository.is_active_member(chat_id, user_id):
        raise MessageAccessDeniedException()
    return chat


class ChatExportPDFView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export full chat as PDF",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: OpenApiResponse(description="PDF binary — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({LIST_MESSAGES}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = list(
            message_repository.get_messages_by_chat(chat_id).order_by("created_at")
        )
        pdf = generate_chat_pdf(chat, messages)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}.pdf"'
        return response


class ChatExportMarkdownView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export full chat as Markdown",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: OpenApiResponse(description="Markdown text — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({LIST_MESSAGES}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = list(message_repository.get_messages_by_chat(chat_id).order_by("created_at"))
        content = generate_chat_markdown(chat, messages)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}.md"'
        return response


class ChatExportJSONView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export full chat as JSON",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: OpenApiResponse(description="JSON backup — Content-Type: application/json"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({LIST_MESSAGES}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = list(message_repository.get_messages_by_chat(chat_id).order_by("created_at"))
        content = generate_chat_json(chat, messages)
        response = HttpResponse(content, content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}.json"'
        return response


class AIResponsesExportView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export AI responses only as Markdown",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={
            200: OpenApiResponse(description="Markdown text — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({LIST_MESSAGES}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = list(message_repository.get_messages_by_chat(chat_id).order_by("created_at"))
        content = generate_ai_responses_markdown(chat, messages)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}_ai.md"'
        return response


class MessageExportPDFView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Export single message as PDF",
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
        AccessControl.require_permissions(request.user, frozenset({LIST_MESSAGES}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        message = message_repository.get_by_id_and_chat(message_id, chat_id)
        if message is None:
            raise MessageNotFoundException()
        pdf = generate_message_pdf(chat, message)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="message_{message_id}.pdf"'
        return response
