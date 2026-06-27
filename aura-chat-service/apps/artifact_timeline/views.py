import logging
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact_timeline.exceptions import TimelineExportException
from apps.artifact_timeline.serializers import (
    GenerateTimelineRequest,
    TimelineGenerateResponse,
    TimelineListResponse,
    TimelineResponse,
)
from apps.artifact_timeline.services.timeline_service import timeline_service
from apps.artifact.audio import transcribe as _transcribe_audio
from apps.artifact_timeline.services.export_service import generate_timeline_markdown, generate_timeline_pdf
from apps.artifact.utils import safe_filename as _safe_filename
from apps.chat.ai_lock_guard import ai_reply_lock_guard
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.chat.ws_rate_limit import check_artifact_rate_limit, check_transcribe_rate_limit
from apps.membership.repositories.membership_repository import membership_repository
from rest_framework.exceptions import ValidationError
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_ID_PARAM = OpenApiParameter(
    name="timeline_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID de la línea de tiempo.",
)
_CHAT_FILTER_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=True,
    description="ID del chat. El usuario debe ser miembro activo del chat.",
)


class TimelineListView(APIView):
    @extend_schema(
        tags=["Timelines"],
        summary="Listar líneas de tiempo",
        description="Devuelve las líneas de tiempo del usuario autenticado, paginadas. Filtrable por chat de origen.",
        parameters=[_CHAT_FILTER_PARAM],
        responses={
            200: TimelineListResponse(many=True),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request) -> Response:
        chat_id_raw = request.query_params.get("chat_id")
        if not chat_id_raw or not chat_id_raw.isdigit():
            raise ValidationError({"chat_id": "Se requiere chat_id válido."})
        chat_id = int(chat_id_raw)
        queryset = timeline_service.list_timelines(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(TimelineListResponse(page, many=True).data)


class TimelineDetailView(APIView):
    @extend_schema(
        tags=["Timelines"],
        summary="Obtener línea de tiempo",
        parameters=[_ID_PARAM],
        responses={
            200: TimelineResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, timeline_id: int) -> Response:
        timeline = timeline_service.get_timeline(user=request.user, timeline_id=timeline_id)
        return Response(TimelineResponse(timeline).data)

    @extend_schema(
        tags=["Timelines"],
        summary="Eliminar línea de tiempo",
        description="Elimina suavemente la línea de tiempo. Solo el creador o un miembro activo del chat de origen puede eliminarla.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, timeline_id: int) -> Response:
        timeline_service.delete_timeline(user=request.user, timeline_id=timeline_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TimelineManageView(APIView):
    @extend_schema(
        tags=["Timelines"],
        summary="Listar todas las líneas de tiempo (admin)",
        description="Lista las líneas de tiempo de todos los usuarios. Requiere permiso `MANAGE_TIMELINES`.",
        responses={
            200: TimelineListResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        queryset = timeline_service.list_all_timelines(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(TimelineListResponse(page, many=True).data)


class TimelineGenerateView(APIView):
    @extend_schema(
        tags=["Timelines"],
        summary="Generar línea de tiempo con IA",
        description=(
                "Genera una línea de tiempo cronológica a partir del mensaje del usuario. "
                "Si se pasa `chat_id`, el historial reciente del chat se incluye como contexto para el LLM "
                "(el usuario debe ser miembro activo). En modo RAG también se usan los documentos del chat. "
                "La línea de tiempo generada queda vinculada al chat via `source_chat_id`. "
                "Requiere permiso `LLM_TIMELINE_GENERATE`."
        ),
        request=GenerateTimelineRequest,
        responses={
            201: TimelineGenerateResponse,
            **standard_error_responses(400, 401, 403, 502),
        },
    )
    def post(self, request: Request) -> Response:
        return async_to_sync(self._post_async)(request)

    async def _post_async(self, request: Request) -> Response:
        serializer = GenerateTimelineRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        chat_id = d["chat_id"]

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        if not await sync_to_async(membership_repository.is_active_contributor)(chat_id, request.user.id):
            raise ChatAccessDeniedException()

        if not await sync_to_async(check_artifact_rate_limit)(request.user.id, chat_id):
            return Response(
                {"detail": "Too many generation requests. Please wait.", "error": "rate_limit_exceeded"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if "audio" in d:
            if not await sync_to_async(check_transcribe_rate_limit)(request.user.id):
                return Response(
                    {"detail": "Too many transcription requests. Please wait.",
                     "error": "transcription_rate_limit_exceeded"},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            message = await sync_to_async(_transcribe_audio)(d["audio"])
        else:
            message = d.get("message", "")

        async with ai_reply_lock_guard(chat_id):
            timeline, messages, fragments = await timeline_service.generate_timeline(
                user=request.user,
                message=message,
                chat_id=chat_id,
                retrieve_context=d.get("retrieve_context"),
                process_documents=d.get("process_documents"),
                document_ids=d.get("document_ids", []),
            )

        return Response(
            TimelineGenerateResponse({"timeline": timeline, "messages": messages, "fragments": fragments}).data,
            status=status.HTTP_201_CREATED,
        )


class TimelineExportPDFView(APIView):
    @extend_schema(
        tags=["Timelines"],
        summary="Exportar línea de tiempo como PDF",
        description="Descarga la línea de tiempo en PDF con los eventos en orden cronológico.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, timeline_id: int) -> HttpResponse:
        timeline = timeline_service.get_own_timeline(user=request.user, timeline_id=timeline_id)
        try:
            pdf = generate_timeline_pdf(timeline)
        except TimelineExportException:
            raise
        safe_title = _safe_filename(timeline.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="timeline_{safe_title}.pdf"'
        return response


class TimelineExportMarkdownView(APIView):
    @extend_schema(
        tags=["Timelines"],
        summary="Exportar línea de tiempo como Markdown",
        description="Descarga la línea de tiempo en formato Markdown.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, timeline_id: int) -> HttpResponse:
        timeline = timeline_service.get_own_timeline(user=request.user, timeline_id=timeline_id)
        content = generate_timeline_markdown(timeline)
        safe_title = _safe_filename(timeline.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="timeline_{safe_title}.md"'
        return response


class TimelineManageExportPDFView(APIView):
    @extend_schema(
        tags=["Timelines"],
        summary="Exportar cualquier línea de tiempo como PDF (admin)",
        description="Descarga la línea de tiempo de cualquier usuario en formato PDF. Requiere permiso `MANAGE_EXPORT_TIMELINE`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, timeline_id: int) -> HttpResponse:
        timeline = timeline_service.get_timeline_admin_export(user=request.user, timeline_id=timeline_id)
        try:
            pdf = generate_timeline_pdf(timeline)
        except TimelineExportException:
            raise
        safe_title = _safe_filename(timeline.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="timeline_{safe_title}.pdf"'
        return response


class TimelineManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Timelines"],
        summary="Exportar cualquier línea de tiempo como Markdown (admin)",
        description="Descarga la línea de tiempo de cualquier usuario en formato Markdown. Requiere permiso `MANAGE_EXPORT_TIMELINE`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, timeline_id: int) -> HttpResponse:
        timeline = timeline_service.get_timeline_admin_export(user=request.user, timeline_id=timeline_id)
        content = generate_timeline_markdown(timeline)
        safe_title = _safe_filename(timeline.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="timeline_{safe_title}.md"'
        return response
