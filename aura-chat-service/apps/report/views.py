import logging

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.report.models import Report
from apps.report.serializers import (
    CreateReportRequest,
    ReportListResponse,
    ReportResponse,
    UpdateReportRequest,
)
from apps.report.services.export_service import generate_report_markdown, generate_report_pdf
from apps.report.services.report_service import report_service
from core.authorization import permissions as perms
from core.authorization.access import AccessControl
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_TYPE_PARAM = OpenApiParameter(
    name="type",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=[Report.Type.SITREP, Report.Type.INTSUM, Report.Type.OPORD],
    description="Filtrar por tipo de informe.",
)
_ID_PARAM = OpenApiParameter(
    name="id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del informe.",
)


class ReportListCreateView(APIView):

    @extend_schema(
        tags=["Reports"],
        summary="Listar informes",
        description="Devuelve los informes del usuario autenticado, paginados. Filtrable por tipo.",
        parameters=[_TYPE_PARAM],
        responses={
            200: ReportListResponse(many=True),
            **standard_error_responses(401),
        },
    )
    def get(self, request: Request) -> Response:
        AccessControl.require_permissions(request.user, frozenset({perms.LIST_REPORTS}))
        report_type = request.query_params.get("type") or None
        queryset = report_service.list_reports(user=request.user, report_type=report_type)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ReportListResponse(page, many=True).data)

    @extend_schema(
        tags=["Reports"],
        summary="Guardar informe",
        description=(
            "Persiste un informe ya generado. "
            "El campo `content` contiene el texto del informe (generalmente producido por el LLM service). "
            "El `title` es opcional: si se omite, se auto-genera desde la primera línea del contenido."
        ),
        request=CreateReportRequest,
        responses={
            201: ReportResponse,
            **standard_error_responses(400, 401),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = CreateReportRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        report = report_service.create_report(
            user=request.user,
            type=d["type"],
            title=d.get("title", ""),
            content=d["content"],
            mode=d["mode"],
            metadata=d.get("metadata", {}),
        )
        return Response(ReportResponse(report).data, status=status.HTTP_201_CREATED)


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
        description="Actualiza el título y/o contenido del informe. Solo el creador puede modificarlo.",
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
        description="Elimina suavemente el informe. Solo el creador puede eliminarlo.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, report_id: int) -> Response:
        report_service.delete_report(user=request.user, report_id=report_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportExportPDFView(APIView):

    @extend_schema(
        tags=["Reports"],
        summary="Exportar informe como PDF",
        description="Descarga el informe en formato PDF con estética de documento militar.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, report_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({perms.EXPORT_REPORT}))
        report = report_service.get_report(user=request.user, report_id=report_id)
        pdf = generate_report_pdf(report)
        safe_title = report.title[:60].replace(" ", "_")
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
        AccessControl.require_permissions(request.user, frozenset({perms.EXPORT_REPORT}))
        report = report_service.get_report(user=request.user, report_id=report_id)
        content = generate_report_markdown(report)
        safe_title = report.title[:60].replace(" ", "_")
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{report.type}_{safe_title}.md"'
        return response
