import logging
import re
from django.conf import settings as _settings
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.membership.repositories.membership_repository import membership_repository
from core.authorization import AccessControl
from core.authorization.permissions import EXPORT_CHAT, MANAGE_CHATS
from core.openapi.common import standard_error_responses

logger = logging.getLogger(__name__)

_MAX_EXPORT_MESSAGES: int = getattr(_settings, "EXPORT_MAX_MESSAGES", 2_000)

_CHAT_ID_PATH_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
)


def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\-]", "_", title[:60])


def _get_chat_or_raise(chat_id: int, user_id: int):
    chat = chat_repository.get_by_id(chat_id)
    if chat is None:
        raise ChatNotFoundException()
    if not membership_repository.is_active_member(chat_id, user_id):
        from apps.artifact_message.exceptions import MessageAccessDeniedException
        raise MessageAccessDeniedException()
    return chat


def _load_messages(chat_id: int):
    from apps.artifact_message.exceptions import ExportTooLargeException
    from apps.artifact_message.repositories.message_repository import message_repository
    qs = message_repository.get_messages_by_chat(chat_id).order_by("created_at")
    messages = list(qs[: _MAX_EXPORT_MESSAGES + 1])
    if len(messages) > _MAX_EXPORT_MESSAGES:
        raise ExportTooLargeException()
    return messages


class ChatExportPDFView(APIView):
    @extend_schema(
        tags=["Chats"],
        summary="Export chat as PDF",
        description="Downloads the full conversation as a PDF attachment. Requires chat membership and `EXPORT_CHAT`.",
        parameters=[_CHAT_ID_PATH_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 413),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        from apps.artifact_message.services.export_service import generate_chat_pdf
        AccessControl.require_permissions(request.user, frozenset({EXPORT_CHAT}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = _load_messages(chat_id)
        pdf = generate_chat_pdf(chat, messages)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}.pdf"'
        return response


class ChatExportMarkdownView(APIView):
    @extend_schema(
        tags=["Chats"],
        summary="Export chat as Markdown",
        description="Downloads the full conversation as Markdown. Requires chat membership and `EXPORT_CHAT`.",
        parameters=[_CHAT_ID_PATH_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404, 413),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        from apps.artifact_message.services.export_service import generate_chat_markdown
        AccessControl.require_permissions(request.user, frozenset({EXPORT_CHAT}))
        chat = _get_chat_or_raise(chat_id, request.user.id)
        messages = _load_messages(chat_id)
        content = generate_chat_markdown(chat, messages)
        safe_title = _safe_filename(chat.name)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="chat_{safe_title}.md"'
        return response


class ChatManageExportPDFView(APIView):
    @extend_schema(
        tags=["Chats"],
        summary="Export chat as PDF (admin)",
        description="Downloads the full conversation as PDF without requiring membership. Requires `MANAGE_CHATS`.",
        parameters=[_CHAT_ID_PATH_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 413),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        from apps.artifact_message.services.export_service import generate_chat_pdf
        AccessControl.require_permissions(request.user, frozenset({MANAGE_CHATS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        messages = _load_messages(chat_id)
        pdf = generate_chat_pdf(chat, messages)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="chat_{chat_id}.pdf"'
        return response


class ChatManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Chats"],
        summary="Export chat as Markdown (admin)",
        description="Downloads the full conversation as Markdown without requiring membership. Requires `MANAGE_CHATS`.",
        parameters=[_CHAT_ID_PATH_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404, 413),
        },
    )
    def get(self, request: Request, chat_id: int) -> HttpResponse:
        from apps.artifact_message.services.export_service import generate_chat_markdown
        AccessControl.require_permissions(request.user, frozenset({MANAGE_CHATS}))
        chat = chat_repository.get_by_id(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        messages = _load_messages(chat_id)
        content = generate_chat_markdown(chat, messages)
        safe_title = _safe_filename(chat.name)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="chat_{safe_title}.md"'
        return response
