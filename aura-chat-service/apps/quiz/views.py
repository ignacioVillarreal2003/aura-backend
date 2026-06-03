import logging
import re
from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.quiz.exceptions import QuizExportException
from apps.quiz.serializers import (
    GenerateQuizRequest,
    QuizGenerateResponse,
    QuizListResponse,
    QuizResponse,
    UpdateQuizRequest,
)
from apps.quiz.services.quiz_service import quiz_service
from apps.message.services.message_service import message_service as _message_service
from apps.quiz.services.export_service import generate_quiz_markdown, generate_quiz_pdf
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_ID_PARAM = OpenApiParameter(
    name="quiz_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del cuestionario.",
)
_CHAT_FILTER_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Filtrar por chat de origen. El usuario debe ser miembro activo del chat.",
)


def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\-]", "_", title[:60])


class QuizListView(APIView):
    @extend_schema(
        tags=["Quizzes"],
        summary="Listar cuestionarios",
        description="Devuelve los cuestionarios del usuario autenticado, paginados. Filtrable por chat de origen.",
        parameters=[_CHAT_FILTER_PARAM],
        responses={
            200: QuizListResponse(many=True),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request) -> Response:
        chat_id_raw = request.query_params.get("chat_id")
        chat_id = int(chat_id_raw) if chat_id_raw and chat_id_raw.isdigit() else None
        queryset = quiz_service.list_quizzes(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(QuizListResponse(page, many=True).data)


class QuizDetailView(APIView):
    @extend_schema(
        tags=["Quizzes"],
        summary="Obtener cuestionario",
        parameters=[_ID_PARAM],
        responses={
            200: QuizResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, quiz_id: int) -> Response:
        quiz = quiz_service.get_quiz(user=request.user, quiz_id=quiz_id)
        return Response(QuizResponse(quiz).data)

    @extend_schema(
        tags=["Quizzes"],
        summary="Actualizar cuestionario",
        description=(
                "Actualiza el título, instrucciones, puntaje mínimo y/o las preguntas. "
                "Enviá el array completo de preguntas con sus opciones. "
                "Solo el creador o miembros del chat de origen pueden modificarlo."
        ),
        parameters=[_ID_PARAM],
        request=UpdateQuizRequest,
        responses={
            200: QuizResponse,
            **standard_error_responses(400, 401, 403, 404),
        },
    )
    def patch(self, request: Request, quiz_id: int) -> Response:
        serializer = UpdateQuizRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        quiz = quiz_service.update_quiz(
            user=request.user,
            quiz_id=quiz_id,
            instructions=d.get("instructions"),
            pass_score=d.get("pass_score"),
            pass_score_provided="pass_score" in d,
            questions=d.get("questions"),
        )
        return Response(QuizResponse(quiz).data)

    @extend_schema(
        tags=["Quizzes"],
        summary="Eliminar cuestionario",
        description="Elimina suavemente el cuestionario. Solo el creador o un miembro activo del chat de origen puede eliminarlo.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, quiz_id: int) -> Response:
        quiz_service.delete_quiz(user=request.user, quiz_id=quiz_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuizManageView(APIView):
    @extend_schema(
        tags=["Quizzes"],
        summary="Listar todos los cuestionarios (admin)",
        description="Lista los cuestionarios de todos los usuarios. Requiere permiso `MANAGE_QUIZZES`.",
        responses={
            200: QuizListResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        queryset = quiz_service.list_all_quizzes(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(QuizListResponse(page, many=True).data)


class QuizGenerateView(APIView):
    @extend_schema(
        tags=["Quizzes"],
        summary="Generar cuestionario con IA",
        description=(
                "Genera un cuestionario de evaluación a partir del mensaje del usuario. "
                "Si se pasa `chat_id`, el historial reciente del chat se incluye como contexto para el LLM "
                "(el usuario debe ser miembro activo). En modo RAG también se usan los documentos del chat. "
                "El cuestionario generado queda vinculado al chat via `source_chat_id`. "
                "Requiere permiso `LLM_QUIZ_GENERATE`."
        ),
        request=GenerateQuizRequest,
        responses={
            201: QuizGenerateResponse,
            **standard_error_responses(400, 401, 403, 502),
        },
    )
    def post(self, request: Request) -> Response:
        return async_to_sync(self._post_async)(request)

    async def _post_async(self, request: Request) -> Response:
        serializer = GenerateQuizRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        if "audio" in d:
            message = await sync_to_async(_message_service.transcribe_audio)(d["audio"])
        else:
            message = d["message"]
        quiz, messages, fragments = await quiz_service.generate_quiz(
            user=request.user,
            message=message,
            mode=d["mode"],
            chat_id=d.get("chat_id"),
        )
        return Response(
            QuizGenerateResponse({"quiz": quiz, "messages": messages, "fragments": fragments}).data,
            status=status.HTTP_201_CREATED,
        )


class QuizExportPDFView(APIView):
    @extend_schema(
        tags=["Quizzes"],
        summary="Exportar cuestionario como PDF",
        description="Descarga el cuestionario en PDF con las respuestas correctas marcadas.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, quiz_id: int) -> HttpResponse:
        quiz = quiz_service.get_own_quiz(user=request.user, quiz_id=quiz_id)
        try:
            pdf = generate_quiz_pdf(quiz)
        except QuizExportException:
            raise
        safe_title = _safe_filename(quiz.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="quiz_{safe_title}.pdf"'
        return response


class QuizExportMarkdownView(APIView):
    @extend_schema(
        tags=["Quizzes"],
        summary="Exportar cuestionario como Markdown",
        description="Descarga el cuestionario en formato Markdown.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, quiz_id: int) -> HttpResponse:
        quiz = quiz_service.get_own_quiz(user=request.user, quiz_id=quiz_id)
        content = generate_quiz_markdown(quiz)
        safe_title = _safe_filename(quiz.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="quiz_{safe_title}.md"'
        return response


class QuizManageExportPDFView(APIView):
    @extend_schema(
        tags=["Quizzes"],
        summary="Exportar cualquier cuestionario como PDF (admin)",
        description="Descarga el cuestionario de cualquier usuario en formato PDF. Requiere permiso `MANAGE_EXPORT_QUIZ`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="PDF — Content-Type: application/pdf"),
            **standard_error_responses(401, 403, 404, 500),
        },
    )
    def get(self, request: Request, quiz_id: int) -> HttpResponse:
        quiz = quiz_service.get_quiz_admin_export(user=request.user, quiz_id=quiz_id)
        try:
            pdf = generate_quiz_pdf(quiz)
        except QuizExportException:
            raise
        safe_title = _safe_filename(quiz.title)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="quiz_{safe_title}.pdf"'
        return response


class QuizManageExportMarkdownView(APIView):
    @extend_schema(
        tags=["Quizzes"],
        summary="Exportar cualquier cuestionario como Markdown (admin)",
        description="Descarga el cuestionario de cualquier usuario en formato Markdown. Requiere permiso `MANAGE_EXPORT_QUIZ`.",
        parameters=[_ID_PARAM],
        responses={
            200: OpenApiResponse(description="Markdown — Content-Type: text/markdown"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, quiz_id: int) -> HttpResponse:
        quiz = quiz_service.get_quiz_admin_export(user=request.user, quiz_id=quiz_id)
        content = generate_quiz_markdown(quiz)
        safe_title = _safe_filename(quiz.title)
        response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="quiz_{safe_title}.md"'
        return response
