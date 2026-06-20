import logging
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact_document_summary.exceptions import DocumentSummaryExportException
from apps.artifact_document_summary.serializers import (
    GenerateDocumentSummaryRequest,
    DocumentSummaryGenerateResponse,
    DocumentSummaryListResponse,
    DocumentSummaryResponse,
)
from apps.artifact_document_summary.services.document_summary_service import document_summary_service
from apps.artifact_document_summary.services.export_service import (
    generate_document_summary_markdown,
    generate_document_summary_pdf,
)
from apps.artifact.utils import safe_filename as _safe_filename
from apps.chat.ai_lock_guard import ai_reply_lock_guard
from apps.chat.exceptions import ChatAccessDeniedException, ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.chat.ws_rate_limit import check_artifact_rate_limit
from apps.membership.repositories.membership_repository import membership_repository
from rest_framework.exceptions import ValidationError
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_ID_PARAM = OpenApiParameter(
    name="document_summary_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del resumen de documento.",
)
_CHAT_FILTER_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=True,
    description="ID del chat. El usuario debe ser miembro activo del chat.",
)


class DocumentSummaryListView(APIView):
    @extend_schema(
        tags=["Document Summaries"],
        summary="Listar resúmenes de documentos",
        description="Devuelve los resúmenes de documentos del chat, paginados.",
        parameters=[_CHAT_FILTER_PARAM],
        responses={
            200: DocumentSummaryListResponse(many=True),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request) -> Response:
        chat_id_raw = request.query_params.get("chat_id")
        if not chat_id_raw or not chat_id_raw.isdigit():
            raise ValidationError({"chat_id": "Se requiere chat_id válido."})
        chat_id = int(chat_id_raw)
        queryset = document_summary_service.list_document_summaries(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(DocumentSummaryListResponse(page, many=True).data)


class DocumentSummaryDetailView(APIView):
    @extend_schema(
        tags=["Document Summaries"],
        summary="Obtener resumen de documento",
        parameters=[_ID_PARAM],
        responses={
            200: DocumentSummaryResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, document_summary_id: int) -> Response:
        obj = document_summary_service.get_document_summary(
            user=request.user, document_summary_id=document_summary_id
        )
        return Response(DocumentSummaryResponse(obj).data)

    @extend_schema(
        tags=["Document Summaries"],
        summary="Eliminar resumen de documento",
        description="Elimina suavemente el resumen. Solo el creador o un miembro activo del chat de origen puede eliminarlo.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, document_summary_id: int) -> Response:
        document_summary_service.delete_document_summary(
            user=request.user, document_summary_id=document_summary_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentSummaryManageView(APIView):
    @extend_schema(
        tags=["Document Summaries"],
        summary="Listar todos los resúmenes (admin)",
        description="Lista los resúmenes de todos los usuarios. Requiere permiso `MANAGE_DOCUMENT_SUMMARIES`.",
        responses={
            200: DocumentSummaryListResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        queryset = document_summary_service.list_all_document_summaries(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(DocumentSummaryListResponse(page, many=True).data)


class DocumentSummaryGenerateView(APIView):
    @extend_schema(
        tags=["Document Summaries"],
        summary="Generar resumen de documento con IA",
        description=(
            "Genera un resumen del contenido de los documentos indicados usando el LLM. "
            "El usuario debe ser miembro activo del chat. "
            "El resumen queda vinculado al chat via `source_chat_id`. "
            "Requiere permiso `LLM_DOCUMENT_SUMMARY_GENERATE`."
        ),
        request=GenerateDocumentSummaryRequest,
        responses={
            201: DocumentSummaryGenerateResponse,
            **standard_error_responses(400, 401, 403, 502),
        },
    )
    def post(self, request: Request) -> Response:
        return async_to_sync(self._post_async)(request)

    async def _post_async(self, request: Request) -> Response:
        serializer = GenerateDocumentSummaryRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        chat_id = d["chat_id"]
        document_ids = d["document_ids"]

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

        async with ai_reply_lock_guard(chat_id):
            obj, fragments = await document_summary_service.generate_document_summary(
                user=request.user,
                document_ids=document_ids,
                chat_id=chat_id,
                retrieve_context=d.get("retrieve_context"),
                process_documents=d.get("process_documents"),
            )

        return Response(
            DocumentSummaryGenerateResponse(
                {"document_summary": obj, "fragments": fragments}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentSummaryExportPDFView(APIView):
    @extend_schema(
        tags=["Document Summaries"],
        summary="Exportar resumen de documento como PDF",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, document_summary_id: int) -> HttpResponse:
        obj = document_summary_service.get_own_document_summary(
            user=request.user, document_summary_id=document_summary_id
        )
        try:
            pdf = generate_document_summary_pdf(obj)
        except DocumentSummaryExportException:
            raise
        safe_title = _safe_filename(obj.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="document_summary_{safe_title}.pdf"'
        return response


class DocumentSummaryExportMarkdownView(APIView):
    @extend_schema(
        tags=["Document Summaries"],
        summary="Exportar resumen de documento como Markdown",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, document_summary_id: int) -> HttpResponse:
        obj = document_summary_service.get_own_document_summary(
            user=request.user, document_summary_id=document_summary_id
        )
        content = generate_document_summary_markdown(obj)
        safe_title = _safe_filename(obj.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="document_summary_{safe_title}.md"'
        return response


class DocumentSummaryManageExportPDFView(APIView):
    @extend_schema(
        tags=["Document Summaries"],
        summary="Exportar cualquier resumen como PDF (admin)",
        description="Requiere permiso `MANAGE_EXPORT_DOCUMENT_SUMMARY`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, document_summary_id: int) -> HttpResponse:
        obj = document_summary_service.get_document_summary_admin_export(
            user=request.user, document_summary_id=document_summary_id
        )
        try:
            pdf = generate_document_summary_pdf(obj)
        except DocumentSummaryExportException:
            raise
        safe_title = _safe_filename(obj.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="document_summary_{safe_title}.pdf"'
        return response


class DocumentSummaryManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Document Summaries"],
        summary="Exportar cualquier resumen como Markdown (admin)",
        description="Requiere permiso `MANAGE_EXPORT_DOCUMENT_SUMMARY`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, document_summary_id: int) -> HttpResponse:
        obj = document_summary_service.get_document_summary_admin_export(
            user=request.user, document_summary_id=document_summary_id
        )
        content = generate_document_summary_markdown(obj)
        safe_title = _safe_filename(obj.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="document_summary_{safe_title}.md"'
        return response
