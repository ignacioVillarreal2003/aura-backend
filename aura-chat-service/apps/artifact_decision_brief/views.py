import logging
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact_decision_brief.exceptions import DecisionBriefExportException
from apps.artifact_decision_brief.serializers import (
    GenerateDecisionBriefRequest,
    DecisionBriefGenerateResponse,
    DecisionBriefListResponse,
    DecisionBriefResponse,
)
from apps.artifact_decision_brief.services.decision_brief_service import decision_brief_service
from apps.artifact.audio import transcribe as _transcribe_audio
from apps.artifact_decision_brief.services.export_service import (
    generate_decision_brief_markdown,
    generate_decision_brief_pdf,
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
    name="decision_brief_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del brief de decisión.",
)
_CHAT_FILTER_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=True,
    description="ID del chat. El usuario debe ser miembro activo del chat.",
)


class DecisionBriefListView(APIView):
    @extend_schema(
        tags=["Decision Briefs"],
        summary="Listar briefs de decisión",
        description="Devuelve los briefs de decisión del usuario autenticado, paginados. Filtrable por chat de origen.",
        parameters=[_CHAT_FILTER_PARAM],
        responses={
            200: DecisionBriefListResponse(many=True),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request) -> Response:
        chat_id_raw = request.query_params.get("chat_id")
        if not chat_id_raw or not chat_id_raw.isdigit():
            raise ValidationError({"chat_id": "Se requiere chat_id válido."})
        chat_id = int(chat_id_raw)
        queryset = decision_brief_service.list_decision_briefs(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(DecisionBriefListResponse(page, many=True).data)


class DecisionBriefDetailView(APIView):
    @extend_schema(
        tags=["Decision Briefs"],
        summary="Obtener brief de decisión",
        parameters=[_ID_PARAM],
        responses={
            200: DecisionBriefResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, decision_brief_id: int) -> Response:
        brief = decision_brief_service.get_decision_brief(user=request.user, decision_brief_id=decision_brief_id)
        return Response(DecisionBriefResponse(brief).data)

    @extend_schema(
        tags=["Decision Briefs"],
        summary="Eliminar brief de decisión",
        description="Elimina suavemente el brief. Solo el creador o un miembro activo del chat de origen puede eliminarlo.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, decision_brief_id: int) -> Response:
        decision_brief_service.delete_decision_brief(user=request.user, decision_brief_id=decision_brief_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DecisionBriefManageView(APIView):
    @extend_schema(
        tags=["Decision Briefs"],
        summary="Listar todos los briefs de decisión (admin)",
        description="Lista los briefs de decisión de todos los usuarios. Requiere permiso `MANAGE_DECISION_BRIEFS`.",
        responses={
            200: DecisionBriefListResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        queryset = decision_brief_service.list_all_decision_briefs(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(DecisionBriefListResponse(page, many=True).data)


class DecisionBriefGenerateView(APIView):
    @extend_schema(
        tags=["Decision Briefs"],
        summary="Generar brief de decisión con IA",
        description=(
                "Genera un documento ejecutivo de decisión a partir del mensaje del usuario. "
                "La IA analiza el material y propone problema, opciones, riesgos y recomendación. "
                "Si se pasa `chat_id`, el historial reciente del chat se incluye como contexto para el LLM "
                "(el usuario debe ser miembro activo). En modo RAG también se usan los documentos del chat. "
                "El brief generado queda vinculado al chat via `source_chat_id`. "
                "Requiere permiso `LLM_DECISION_BRIEF_GENERATE`."
        ),
        request=GenerateDecisionBriefRequest,
        responses={
            201: DecisionBriefGenerateResponse,
            **standard_error_responses(400, 401, 403, 502),
        },
    )
    def post(self, request: Request) -> Response:
        return async_to_sync(self._post_async)(request)

    async def _post_async(self, request: Request) -> Response:
        serializer = GenerateDecisionBriefRequest(data=request.data)
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
            brief, messages, fragments = await decision_brief_service.generate_decision_brief(
                user=request.user,
                message=message,
                chat_id=chat_id,
                retrieve_context=d.get("retrieve_context"),
                process_documents=d.get("process_documents"),
                document_ids=d.get("document_ids", []),
            )

        return Response(
            DecisionBriefGenerateResponse(
                {"decision_brief": brief, "messages": messages, "fragments": fragments}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class DecisionBriefExportPDFView(APIView):
    @extend_schema(
        tags=["Decision Briefs"],
        summary="Exportar brief de decisión como PDF",
        description="Descarga el brief de decisión en formato PDF ejecutivo.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, decision_brief_id: int) -> HttpResponse:
        brief = decision_brief_service.get_own_decision_brief(user=request.user, decision_brief_id=decision_brief_id)
        try:
            pdf = generate_decision_brief_pdf(brief)
        except DecisionBriefExportException:
            raise
        safe_title = _safe_filename(brief.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="decision_brief_{safe_title}.pdf"'
        return response


class DecisionBriefExportMarkdownView(APIView):
    @extend_schema(
        tags=["Decision Briefs"],
        summary="Exportar brief de decisión como Markdown",
        description="Descarga el brief de decisión en formato Markdown.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, decision_brief_id: int) -> HttpResponse:
        brief = decision_brief_service.get_own_decision_brief(user=request.user, decision_brief_id=decision_brief_id)
        content = generate_decision_brief_markdown(brief)
        safe_title = _safe_filename(brief.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="decision_brief_{safe_title}.md"'
        return response


class DecisionBriefManageExportPDFView(APIView):
    @extend_schema(
        tags=["Decision Briefs"],
        summary="Exportar cualquier brief de decisión como PDF (admin)",
        description="Descarga el brief de cualquier usuario en formato PDF. Requiere permiso `MANAGE_EXPORT_DECISION_BRIEF`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, decision_brief_id: int) -> HttpResponse:
        brief = decision_brief_service.get_decision_brief_admin_export(
            user=request.user, decision_brief_id=decision_brief_id
        )
        try:
            pdf = generate_decision_brief_pdf(brief)
        except DecisionBriefExportException:
            raise
        safe_title = _safe_filename(brief.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="decision_brief_{safe_title}.pdf"'
        return response


class DecisionBriefManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Decision Briefs"],
        summary="Exportar cualquier brief de decisión como Markdown (admin)",
        description="Descarga el brief de cualquier usuario en formato Markdown. Requiere permiso `MANAGE_EXPORT_DECISION_BRIEF`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, decision_brief_id: int) -> HttpResponse:
        brief = decision_brief_service.get_decision_brief_admin_export(
            user=request.user, decision_brief_id=decision_brief_id
        )
        content = generate_decision_brief_markdown(brief)
        safe_title = _safe_filename(brief.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="decision_brief_{safe_title}.md"'
        return response
