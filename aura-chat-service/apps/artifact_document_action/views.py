import logging
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact_document_action.exceptions import DocumentActionExportException
from apps.artifact_document_action.serializers import (
    GenerateDocumentActionRequest,
    DocumentActionGenerateResponse,
    DocumentActionListResponse,
    DocumentActionResponse,
)
from apps.artifact_document_action.services.document_action_service import document_action_service
from apps.artifact_document_action.services.export_service import (
    generate_document_action_markdown,
    generate_document_action_pdf,
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
    name="document_action_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID de la acción sobre documento.",
)
_CHAT_FILTER_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=True,
    description="ID del chat. El usuario debe ser miembro activo del chat.",
)


class DocumentActionListView(APIView):
    @extend_schema(
        tags=["Document Actions"],
        summary="Listar acciones sobre documentos",
        description="Devuelve las acciones sobre documentos del chat, paginadas.",
        parameters=[_CHAT_FILTER_PARAM],
        responses={
            200: DocumentActionListResponse(many=True),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request) -> Response:
        chat_id_raw = request.query_params.get("chat_id")
        if not chat_id_raw or not chat_id_raw.isdigit():
            raise ValidationError({"chat_id": "Se requiere chat_id válido."})
        chat_id = int(chat_id_raw)
        queryset = document_action_service.list_document_actions(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(DocumentActionListResponse(page, many=True).data)


class DocumentActionDetailView(APIView):
    @extend_schema(
        tags=["Document Actions"],
        summary="Obtener acción sobre documento",
        parameters=[_ID_PARAM],
        responses={
            200: DocumentActionResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, document_action_id: int) -> Response:
        obj = document_action_service.get_document_action(
            user=request.user, document_action_id=document_action_id
        )
        return Response(DocumentActionResponse(obj).data)

    @extend_schema(
        tags=["Document Actions"],
        summary="Eliminar acción sobre documento",
        description="Elimina suavemente la acción. Solo el creador o un miembro activo del chat de origen puede eliminarla.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, document_action_id: int) -> Response:
        document_action_service.delete_document_action(
            user=request.user, document_action_id=document_action_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentActionManageView(APIView):
    @extend_schema(
        tags=["Document Actions"],
        summary="Listar todas las acciones sobre documentos (admin)",
        description="Lista las acciones de todos los usuarios. Requiere permiso `MANAGE_DOCUMENT_ACTIONS`.",
        responses={
            200: DocumentActionListResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        queryset = document_action_service.list_all_document_actions(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(DocumentActionListResponse(page, many=True).data)


class DocumentActionGenerateView(APIView):
    @extend_schema(
        tags=["Document Actions"],
        summary="Ejecutar acción sobre documentos con IA",
        description=(
            "Ejecuta una acción estructurada sobre los documentos indicados usando el LLM. "
            "Proporcionar `instruction` con la tarea a realizar e, opcionalmente, `action` "
            "para preconfigurar el tipo de operación. "
            "El usuario debe ser miembro activo del chat. "
            "El resultado queda vinculado al chat via `source_chat_id`. "
            "Requiere permiso `LLM_DOCUMENT_ACTION_GENERATE`."
        ),
        request=GenerateDocumentActionRequest,
        responses={
            201: DocumentActionGenerateResponse,
            **standard_error_responses(400, 401, 403, 502),
        },
    )
    def post(self, request: Request) -> Response:
        return async_to_sync(self._post_async)(request)

    async def _post_async(self, request: Request) -> Response:
        serializer = GenerateDocumentActionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        chat_id = d["chat_id"]
        document_ids = d["document_ids"]
        instruction = d["instruction"]
        action = d.get("action")

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
            obj, fragments = await document_action_service.generate_document_action(
                user=request.user,
                document_ids=document_ids,
                instruction=instruction,
                action=action,
                chat_id=chat_id,
                retrieve_context=d.get("retrieve_context"),
                process_documents=d.get("process_documents"),
            )

        return Response(
            DocumentActionGenerateResponse(
                {"document_action": obj, "fragments": fragments}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentActionExportPDFView(APIView):
    @extend_schema(
        tags=["Document Actions"],
        summary="Exportar acción sobre documento como PDF",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, document_action_id: int) -> HttpResponse:
        obj = document_action_service.get_own_document_action(
            user=request.user, document_action_id=document_action_id
        )
        try:
            pdf = generate_document_action_pdf(obj)
        except DocumentActionExportException:
            raise
        safe_title = _safe_filename(obj.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="document_action_{safe_title}.pdf"'
        return response


class DocumentActionExportMarkdownView(APIView):
    @extend_schema(
        tags=["Document Actions"],
        summary="Exportar acción sobre documento como Markdown",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, document_action_id: int) -> HttpResponse:
        obj = document_action_service.get_own_document_action(
            user=request.user, document_action_id=document_action_id
        )
        content = generate_document_action_markdown(obj)
        safe_title = _safe_filename(obj.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="document_action_{safe_title}.md"'
        return response


class DocumentActionManageExportPDFView(APIView):
    @extend_schema(
        tags=["Document Actions"],
        summary="Exportar cualquier acción sobre documento como PDF (admin)",
        description="Requiere permiso `MANAGE_EXPORT_DOCUMENT_ACTION`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, document_action_id: int) -> HttpResponse:
        obj = document_action_service.get_document_action_admin_export(
            user=request.user, document_action_id=document_action_id
        )
        try:
            pdf = generate_document_action_pdf(obj)
        except DocumentActionExportException:
            raise
        safe_title = _safe_filename(obj.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="document_action_{safe_title}.pdf"'
        return response


class DocumentActionManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Document Actions"],
        summary="Exportar cualquier acción sobre documento como Markdown (admin)",
        description="Requiere permiso `MANAGE_EXPORT_DOCUMENT_ACTION`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, document_action_id: int) -> HttpResponse:
        obj = document_action_service.get_document_action_admin_export(
            user=request.user, document_action_id=document_action_id
        )
        content = generate_document_action_markdown(obj)
        safe_title = _safe_filename(obj.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="document_action_{safe_title}.md"'
        return response
