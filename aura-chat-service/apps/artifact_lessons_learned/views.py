import logging
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact_lessons_learned.exceptions import LessonsLearnedExportException
from apps.artifact_lessons_learned.serializers import (
    GenerateLessonsLearnedRequest,
    LessonsLearnedGenerateResponse,
    LessonsLearnedListResponse,
    LessonsLearnedResponse,
)
from apps.artifact_lessons_learned.services.lessons_learned_service import lessons_learned_service
from apps.artifact.audio import transcribe as _transcribe_audio
from apps.artifact_lessons_learned.services.export_service import (
    generate_lessons_learned_markdown,
    generate_lessons_learned_pdf,
)
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
    name="lessons_learned_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID de las lecciones aprendidas.",
)
_CHAT_FILTER_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=True,
    description="ID del chat. El usuario debe ser miembro activo del chat.",
)


class LessonsLearnedListView(APIView):
    @extend_schema(
        tags=["Lessons Learned"],
        summary="Listar lecciones aprendidas",
        description="Devuelve las lecciones aprendidas del usuario autenticado, paginadas. Filtrable por chat de origen.",
        parameters=[_CHAT_FILTER_PARAM],
        responses={
            200: LessonsLearnedListResponse(many=True),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request) -> Response:
        chat_id_raw = request.query_params.get("chat_id")
        if not chat_id_raw or not chat_id_raw.isdigit():
            raise ValidationError({"chat_id": "Se requiere chat_id válido."})
        chat_id = int(chat_id_raw)
        queryset = lessons_learned_service.list_lessons_learned(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(LessonsLearnedListResponse(page, many=True).data)


class LessonsLearnedDetailView(APIView):
    @extend_schema(
        tags=["Lessons Learned"],
        summary="Obtener lecciones aprendidas",
        parameters=[_ID_PARAM],
        responses={
            200: LessonsLearnedResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, lessons_learned_id: int) -> Response:
        ll = lessons_learned_service.get_lessons_learned(user=request.user, lessons_learned_id=lessons_learned_id)
        return Response(LessonsLearnedResponse(ll).data)

    @extend_schema(
        tags=["Lessons Learned"],
        summary="Eliminar lecciones aprendidas",
        description="Elimina suavemente las lecciones aprendidas. Solo el creador o un miembro activo del chat de origen puede eliminarlas.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, lessons_learned_id: int) -> Response:
        lessons_learned_service.delete_lessons_learned(user=request.user, lessons_learned_id=lessons_learned_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LessonsLearnedManageView(APIView):
    @extend_schema(
        tags=["Lessons Learned"],
        summary="Listar todas las lecciones aprendidas (admin)",
        description="Lista las lecciones aprendidas de todos los usuarios. Requiere permiso `MANAGE_LESSONS_LEARNED`.",
        responses={
            200: LessonsLearnedListResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        queryset = lessons_learned_service.list_all_lessons_learned(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(LessonsLearnedListResponse(page, many=True).data)


class LessonsLearnedGenerateView(APIView):
    @extend_schema(
        tags=["Lessons Learned"],
        summary="Generar lecciones aprendidas con IA",
        description=(
                "Genera un análisis de lecciones aprendidas a partir del mensaje del usuario. "
                "Si se pasa `chat_id`, el historial reciente del chat se incluye como contexto para el LLM "
                "(el usuario debe ser miembro activo). En modo RAG también se usan los documentos del chat. "
                "El resultado queda vinculado al chat via `source_chat_id`. "
                "Requiere permiso `LLM_LESSONS_LEARNED_GENERATE`."
        ),
        request=GenerateLessonsLearnedRequest,
        responses={
            201: LessonsLearnedGenerateResponse,
            **standard_error_responses(400, 401, 403, 502),
        },
    )
    def post(self, request: Request) -> Response:
        return async_to_sync(self._post_async)(request)

    async def _post_async(self, request: Request) -> Response:
        serializer = GenerateLessonsLearnedRequest(data=request.data)
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
            ll, messages, fragments = await lessons_learned_service.generate_lessons_learned(
                user=request.user,
                message=message,
                chat_id=chat_id,
                retrieve_context=d.get("retrieve_context"),
                process_documents=d.get("process_documents"),
                document_ids=d.get("document_ids", []),
            )

        return Response(
            LessonsLearnedGenerateResponse(
                {"lessons_learned": ll, "messages": messages, "fragments": fragments}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class LessonsLearnedExportPDFView(APIView):
    @extend_schema(
        tags=["Lessons Learned"],
        summary="Exportar lecciones aprendidas como PDF",
        description="Descarga las lecciones aprendidas en PDF agrupadas por categoría.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, lessons_learned_id: int) -> HttpResponse:
        ll = lessons_learned_service.get_own_lessons_learned(user=request.user, lessons_learned_id=lessons_learned_id)
        try:
            pdf = generate_lessons_learned_pdf(ll)
        except LessonsLearnedExportException:
            raise
        safe_title = _safe_filename(ll.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="lessons_learned_{safe_title}.pdf"'
        return response


class LessonsLearnedExportMarkdownView(APIView):
    @extend_schema(
        tags=["Lessons Learned"],
        summary="Exportar lecciones aprendidas como Markdown",
        description="Descarga las lecciones aprendidas en formato Markdown.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, lessons_learned_id: int) -> HttpResponse:
        ll = lessons_learned_service.get_own_lessons_learned(user=request.user, lessons_learned_id=lessons_learned_id)
        content = generate_lessons_learned_markdown(ll)
        safe_title = _safe_filename(ll.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="lessons_learned_{safe_title}.md"'
        return response


class LessonsLearnedManageExportPDFView(APIView):
    @extend_schema(
        tags=["Lessons Learned"],
        summary="Exportar cualquier lecciones aprendidas como PDF (admin)",
        description="Descarga las lecciones aprendidas de cualquier usuario en PDF. Requiere permiso `MANAGE_EXPORT_LESSONS_LEARNED`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, lessons_learned_id: int) -> HttpResponse:
        ll = lessons_learned_service.get_lessons_learned_admin_export(
            user=request.user, lessons_learned_id=lessons_learned_id
        )
        try:
            pdf = generate_lessons_learned_pdf(ll)
        except LessonsLearnedExportException:
            raise
        safe_title = _safe_filename(ll.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="lessons_learned_{safe_title}.pdf"'
        return response


class LessonsLearnedManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Lessons Learned"],
        summary="Exportar cualquier lecciones aprendidas como Markdown (admin)",
        description="Descarga las lecciones aprendidas de cualquier usuario en Markdown. Requiere permiso `MANAGE_EXPORT_LESSONS_LEARNED`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, lessons_learned_id: int) -> HttpResponse:
        ll = lessons_learned_service.get_lessons_learned_admin_export(
            user=request.user, lessons_learned_id=lessons_learned_id
        )
        content = generate_lessons_learned_markdown(ll)
        safe_title = _safe_filename(ll.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="lessons_learned_{safe_title}.md"'
        return response
