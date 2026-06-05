import logging
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact_checklist.exceptions import ChecklistExportException
from apps.artifact_checklist.serializers import (
    ChecklistGenerateResponse,
    ChecklistListResponse,
    ChecklistResponse,
    GenerateChecklistRequest,
    UpdateChecklistRequest,
)
from apps.artifact_checklist.services.checklist_service import checklist_service
from apps.artifact.audio import transcribe as _transcribe_audio
from apps.artifact_checklist.services.export_service import generate_checklist_markdown, generate_checklist_pdf
from apps.artifact.utils import safe_filename as _safe_filename
from apps.chat.ai_reply_lock import release, try_acquire
from apps.chat.exceptions import ChatAiReplyInProgressException
from apps.chat.ws_rate_limit import check_artifact_rate_limit, check_transcribe_rate_limit
from apps.artifact_message.services.message_service import broadcast_chat_ai_lock_change
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_ID_PARAM = OpenApiParameter(
    name="checklist_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID de la checklist.",
)
_CHAT_FILTER_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Filtrar por chat de origen. El usuario debe ser miembro activo del chat.",
)


class ChecklistListView(APIView):
    @extend_schema(
        tags=["Checklists"],
        summary="Listar checklists",
        description="Devuelve las checklists del usuario autenticado, paginadas. Filtrable por chat de origen.",
        parameters=[_CHAT_FILTER_PARAM],
        responses={
            200: ChecklistListResponse(many=True),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request) -> Response:
        chat_id_raw = request.query_params.get("chat_id")
        chat_id = int(chat_id_raw) if chat_id_raw and chat_id_raw.isdigit() else None
        queryset = checklist_service.list_checklists(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ChecklistListResponse(page, many=True).data)


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
                "Enviá el array completo de ítems con los estados actualizados. "
                "Solo el creador o miembros del chat de origen pueden modificarla."
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
            sections=d.get("sections"),
        )
        return Response(ChecklistResponse(checklist).data)

    @extend_schema(
        tags=["Checklists"],
        summary="Eliminar checklist",
        description="Elimina suavemente la checklist. Solo el creador o un miembro activo del chat de origen puede eliminarla.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, checklist_id: int) -> Response:
        checklist_service.delete_checklist(user=request.user, checklist_id=checklist_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChecklistManageView(APIView):
    @extend_schema(
        tags=["Checklists"],
        summary="Listar todas las checklists (admin)",
        description="Lista las checklists de todos los usuarios. Requiere permiso `MANAGE_CHECKLISTS`.",
        responses={
            200: ChecklistListResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        queryset = checklist_service.list_all_checklists(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ChecklistListResponse(page, many=True).data)


class ChecklistGenerateView(APIView):
    @extend_schema(
        tags=["Checklists"],
        summary="Generar checklist con IA",
        description=(
                "Genera una checklist estructurada a partir del mensaje del usuario. "
                "Si se pasa `chat_id`, el historial reciente del chat se incluye como contexto para el LLM "
                "(el usuario debe ser miembro activo). En modo RAG también se usan los documentos del chat. "
                "La checklist generada queda vinculada al chat via `source_chat_id`. "
                "Requiere permiso `LLM_CHECKLIST_GENERATE`."
        ),
        request=GenerateChecklistRequest,
        responses={
            201: ChecklistGenerateResponse,
            **standard_error_responses(400, 401, 403, 502),
        },
    )
    def post(self, request: Request) -> Response:
        return async_to_sync(self._post_async)(request)

    async def _post_async(self, request: Request) -> Response:
        serializer = GenerateChecklistRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        chat_id = d["chat_id"]

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

        await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, True)
        try:
            checklist, messages, fragments = await checklist_service.generate_checklist(
                user=request.user,
                message=message,
                mode=d["mode"],
                chat_id=chat_id,
            )
        finally:
            await sync_to_async(release)(chat_id)
            await sync_to_async(broadcast_chat_ai_lock_change)(chat_id, False)

        return Response(
            ChecklistGenerateResponse({"checklist": checklist, "messages": messages, "fragments": fragments}).data,
            status=status.HTTP_201_CREATED,
        )


class ChecklistExportPDFView(APIView):
    @extend_schema(
        tags=["Checklists"],
        summary="Exportar checklist como PDF",
        description="Descarga la checklist en PDF con marca de verificación por ítem.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, checklist_id: int) -> HttpResponse:
        checklist = checklist_service.get_own_checklist(user=request.user, checklist_id=checklist_id)
        try:
            pdf = generate_checklist_pdf(checklist)
        except ChecklistExportException:
            raise
        safe_title = _safe_filename(checklist.artifact.title)
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
        checklist = checklist_service.get_own_checklist(user=request.user, checklist_id=checklist_id)
        content = generate_checklist_markdown(checklist)
        safe_title = _safe_filename(checklist.artifact.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="checklist_{safe_title}.md"'
        return response


class ChecklistManageExportPDFView(APIView):
    @extend_schema(
        tags=["Checklists"],
        summary="Exportar cualquier checklist como PDF (admin)",
        description="Descarga la checklist de cualquier usuario en formato PDF. Requiere permiso `MANAGE_EXPORT_CHECKLIST`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, checklist_id: int) -> HttpResponse:
        checklist = checklist_service.get_checklist_admin_export(user=request.user, checklist_id=checklist_id)
        try:
            pdf = generate_checklist_pdf(checklist)
        except ChecklistExportException:
            raise
        safe_title = _safe_filename(checklist.artifact.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="checklist_{safe_title}.pdf"'
        return response


class ChecklistManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Checklists"],
        summary="Exportar cualquier checklist como Markdown (admin)",
        description="Descarga la checklist de cualquier usuario en formato Markdown. Requiere permiso `MANAGE_EXPORT_CHECKLIST`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, checklist_id: int) -> HttpResponse:
        checklist = checklist_service.get_checklist_admin_export(user=request.user, checklist_id=checklist_id)
        content = generate_checklist_markdown(checklist)
        safe_title = _safe_filename(checklist.artifact.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="checklist_{safe_title}.md"'
        return response
