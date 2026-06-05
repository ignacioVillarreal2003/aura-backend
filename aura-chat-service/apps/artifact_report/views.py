import logging
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact_report.exceptions import ReportExportException
from apps.artifact_report.models import ArtifactReport
from apps.artifact_report.serializers import (
    GenerateReportRequest,
    ReportGenerateResponse,
    ReportListResponse,
    ReportResponse,
    UpdateReportRequest,
)
from apps.artifact.audio import transcribe as _transcribe_audio
from apps.artifact_report.services.export_service import generate_report_markdown, generate_report_pdf
from apps.artifact_report.services.report_service import report_service
from apps.artifact.utils import safe_filename as _safe_filename
from apps.chat.ai_reply_lock import release, try_acquire
from apps.chat.exceptions import ChatAccessDeniedException, ChatAiReplyInProgressException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.chat.ws_rate_limit import check_artifact_rate_limit, check_transcribe_rate_limit
from apps.artifact_message.services.message_service import broadcast_chat_ai_lock_change
from apps.membership.repositories.membership_repository import membership_repository
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_TYPE_PARAM = OpenApiParameter(
    name="type",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=[ArtifactReport.Type.SITREP, ArtifactReport.Type.INTSUM, ArtifactReport.Type.OPORD],
    description="Filtrar por tipo de informe.",
)
_CHAT_FILTER_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Filtrar por chat de origen. El usuario debe ser miembro activo del chat.",
)
_ID_PARAM = OpenApiParameter(
    name="report_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del informe.",
)


class ReportListView(APIView):
    @extend_schema(
        tags=["Reports"],
        summary="Listar informes",
        description="Devuelve los informes del usuario autenticado, paginados. Filtrable por tipo y por chat de origen.",
        parameters=[_TYPE_PARAM, _CHAT_FILTER_PARAM],
        responses={
            200: ReportListResponse(many=True),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request) -> Response:
        report_type = request.query_params.get("type") or None
        chat_id_raw = request.query_params.get("chat_id")
        chat_id = int(chat_id_raw) if chat_id_raw and chat_id_raw.isdigit() else None
        queryset = report_service.list_reports(user=request.user, report_type=report_type, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ReportListResponse(page, many=True).data)


class ReportDetailView(APIView):
    @extend_schema(
        tags=["Reports"],
        summary="Obtener informe",
        parameters=[_ID_PARAM],
        responses={
            200: ReportResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, report_id: int) -> Response:
        report = report_service.get_report(user=request.user, report_id=report_id)
        return Response(ReportResponse(report).data)

    @extend_schema(
        tags=["Reports"],
        summary="Actualizar informe",
        description="Actualiza el título y/o contenido del informe. Solo el creador o miembros del chat de origen pueden modificarlo.",
        parameters=[_ID_PARAM],
        request=UpdateReportRequest,
        responses={
            200: ReportResponse,
            **standard_error_responses(400, 401, 403, 404),
        },
    )
    def patch(self, request: Request, report_id: int) -> Response:
        serializer = UpdateReportRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        report = report_service.update_report(
            user=request.user,
            report_id=report_id,
            title=d.get("title"),
            content=d.get("content"),
        )
        return Response(ReportResponse(report).data)

    @extend_schema(
        tags=["Reports"],
        summary="Eliminar informe",
        description="Elimina suavemente el informe. Solo el creador o un miembro activo con rol owner o editor puede eliminarlo.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, report_id: int) -> Response:
        report_service.delete_report(user=request.user, report_id=report_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportManageView(APIView):
    @extend_schema(
        tags=["Reports"],
        summary="Listar todos los informes (admin)",
        description="Lista los informes de todos los usuarios. Requiere permiso `MANAGE_REPORTS`.",
        parameters=[_TYPE_PARAM],
        responses={
            200: ReportListResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        report_type = request.query_params.get("type") or None
        queryset = report_service.list_all_reports(user=request.user, report_type=report_type)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ReportListResponse(page, many=True).data)


class ReportGenerateView(APIView):
    @extend_schema(
        tags=["Reports"],
        summary="Generar informe con IA",
        description=(
                "Genera un informe estandarizado (SITREP, INTSUM u OPORD) a partir del mensaje del usuario. "
                "Si se pasa `chat_id`, el historial reciente del chat se incluye como contexto para el LLM "
                "(el usuario debe ser miembro activo). En modo RAG también se usan los documentos del chat. "
                "El informe generado queda vinculado al chat via `source_chat_id`. "
                "Requiere permiso `LLM_REPORT_GENERATE`."
        ),
        request=GenerateReportRequest,
        responses={
            201: ReportGenerateResponse,
            **standard_error_responses(400, 401, 403, 502),
        },
    )
    def post(self, request: Request) -> Response:
        return async_to_sync(self._post_async)(request)

    async def _post_async(self, request: Request) -> Response:
        serializer = GenerateReportRequest(data=request.data)
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
                    {"detail": "Too many transcription requests. Please wait.", "error": "transcription_rate_limit_exceeded"},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            message = await sync_to_async(_transcribe_audio)(d["audio"])
        else:
            message = d["message"]

        if not await sync_to_async(try_acquire)(chat_id):
            raise ChatAiReplyInProgressException()

        try:
            await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, True)
            report, messages, fragments = await report_service.generate_report(
                user=request.user,
                report_type=d["type"],
                message=message,
                mode=d["mode"],
                chat_id=chat_id,
            )
        finally:
            await sync_to_async(release)(chat_id)
            await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, False)

        return Response(
            ReportGenerateResponse({"report": report, "messages": messages, "fragments": fragments}).data,
            status=status.HTTP_201_CREATED,
        )


class ReportExportPDFView(APIView):
    @extend_schema(
        tags=["Reports"],
        summary="Exportar informe como PDF",
        description="Descarga el informe en formato PDF con estética de documento militar.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, report_id: int) -> HttpResponse:
        report = report_service.get_own_report(user=request.user, report_id=report_id)
        try:
            pdf = generate_report_pdf(report)
        except ReportExportException:
            raise
        safe_title = _safe_filename(report.artifact.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{report.type}_{safe_title}.pdf"'
        return response


class ReportExportMarkdownView(APIView):
    @extend_schema(
        tags=["Reports"],
        summary="Exportar informe como Markdown",
        description="Descarga el informe en formato Markdown.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, report_id: int) -> HttpResponse:
        report = report_service.get_own_report(user=request.user, report_id=report_id)
        content = generate_report_markdown(report)
        safe_title = _safe_filename(report.artifact.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{report.type}_{safe_title}.md"'
        return response


class ReportManageExportPDFView(APIView):
    @extend_schema(
        tags=["Reports"],
        summary="Exportar cualquier informe como PDF (admin)",
        description="Descarga el informe de cualquier usuario en formato PDF. Requiere permiso `MANAGE_EXPORT_REPORT`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, report_id: int) -> HttpResponse:
        report = report_service.get_report_admin_export(user=request.user, report_id=report_id)
        try:
            pdf = generate_report_pdf(report)
        except ReportExportException:
            raise
        safe_title = _safe_filename(report.artifact.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{report.type}_{safe_title}.pdf"'
        return response


class ReportManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Reports"],
        summary="Exportar cualquier informe como Markdown (admin)",
        description="Descarga el informe de cualquier usuario en formato Markdown. Requiere permiso `MANAGE_EXPORT_REPORT`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, report_id: int) -> HttpResponse:
        report = report_service.get_report_admin_export(user=request.user, report_id=report_id)
        content = generate_report_markdown(report)
        safe_title = _safe_filename(report.artifact.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{report.type}_{safe_title}.md"'
        return response
