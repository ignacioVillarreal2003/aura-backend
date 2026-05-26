import logging

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.checklist.serializers import (
    ChecklistListResponse,
    ChecklistResponse,
    CreateChecklistRequest,
    UpdateChecklistRequest,
)
from apps.checklist.services.checklist_service import checklist_service
from apps.checklist.services.export_service import generate_checklist_markdown, generate_checklist_pdf
from core.authorization import permissions as perms
from core.authorization.access import AccessControl
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_ID_PARAM = OpenApiParameter(
    name="id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID de la checklist.",
)


class ChecklistListCreateView(APIView):

    @extend_schema(
        tags=["Checklists"],
        summary="Listar checklists",
        description="Devuelve las checklists del usuario autenticado, paginadas.",
        responses={
            200: ChecklistListResponse(many=True),
            **standard_error_responses(401),
        },
    )
    def get(self, request: Request) -> Response:
        AccessControl.require_permissions(request.user, frozenset({perms.LIST_CHECKLISTS}))
        queryset = checklist_service.list_checklists(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ChecklistListResponse(page, many=True).data)

    @extend_schema(
        tags=["Checklists"],
        summary="Guardar checklist",
        description=(
            "Persiste una checklist generada por el LLM service. "
            "Los ítems incluyen el estado de verificación (`is_checked`) y notas opcionales."
        ),
        request=CreateChecklistRequest,
        responses={
            201: ChecklistResponse,
            **standard_error_responses(400, 401),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = CreateChecklistRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        checklist = checklist_service.create_checklist(
            user=request.user,
            title=d["title"],
            items=d["items"],
            mode=d["mode"],
            metadata=d.get("metadata", {}),
        )
        return Response(ChecklistResponse(checklist).data, status=status.HTTP_201_CREATED)


class ChecklistDetailView(APIView):

    @extend_schema(
        tags=["Checklists"],
        summary="Obtener checklist",
        parameters=[_ID_PARAM],
        responses={
            200: ChecklistResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, checklist_id: int) -> Response:
        checklist = checklist_service.get_checklist(user=request.user, checklist_id=checklist_id)
        return Response(ChecklistResponse(checklist).data)

    @extend_schema(
        tags=["Checklists"],
        summary="Actualizar checklist",
        description=(
            "Actualiza el título y/o los ítems de la checklist. "
            "Enviá el array completo de ítems con los estados actualizados."
        ),
        parameters=[_ID_PARAM],
        request=UpdateChecklistRequest,
        responses={
            200: ChecklistResponse,
            **standard_error_responses(400, 401, 403, 404),
        },
    )
    def patch(self, request: Request, checklist_id: int) -> Response:
        serializer = UpdateChecklistRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        checklist = checklist_service.update_checklist(
            user=request.user,
            checklist_id=checklist_id,
            title=d.get("title"),
            items=d.get("items"),
        )
        return Response(ChecklistResponse(checklist).data)

    @extend_schema(
        tags=["Checklists"],
        summary="Eliminar checklist",
        description="Elimina suavemente la checklist. Solo el creador puede eliminarla.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, checklist_id: int) -> Response:
        checklist_service.delete_checklist(user=request.user, checklist_id=checklist_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChecklistExportPDFView(APIView):

    @extend_schema(
        tags=["Checklists"],
        summary="Exportar checklist como PDF",
        description="Descarga la checklist en PDF con marca de verificación por ítem.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, checklist_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({perms.EXPORT_CHECKLIST}))
        checklist = checklist_service.get_checklist(user=request.user, checklist_id=checklist_id)
        pdf = generate_checklist_pdf(checklist)
        safe_title = checklist.title[:60].replace(" ", "_")
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="checklist_{safe_title}.pdf"'
        return response


class ChecklistExportMarkdownView(APIView):

    @extend_schema(
        tags=["Checklists"],
        summary="Exportar checklist como Markdown",
        description="Descarga la checklist en formato Markdown con checkboxes.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, checklist_id: int) -> HttpResponse:
        AccessControl.require_permissions(request.user, frozenset({perms.EXPORT_CHECKLIST}))
        checklist = checklist_service.get_checklist(user=request.user, checklist_id=checklist_id)
        content = generate_checklist_markdown(checklist)
        safe_title = checklist.title[:60].replace(" ", "_")
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="checklist_{safe_title}.md"'
        return response
