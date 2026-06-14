from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact.serializers import ArtifactSummaryResponse
from apps.artifact.services.artifact_service import artifact_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

_CHAT_ID_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del chat.",
)


class ChatFeedView(APIView):
    @extend_schema(
        tags=["Chat"],
        summary="Feed unificado del chat",
        description=(
                "Devuelve todos los artefactos del chat (mensajes, informes, checklists, "
                "quizzes, timelines, lecciones aprendidas, decision briefs, resúmenes y "
                "acciones de documentos) ordenados "
                "cronológicamente. El usuario debe ser miembro activo del chat y tener "
                "el permiso `LIST_ARTIFACTS`."
        ),
        parameters=[_CHAT_ID_PARAM],
        responses={
            200: ArtifactSummaryResponse(many=True),
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, chat_id: int) -> Response:
        qs = artifact_service.list_chat_artifacts(
            user=request.user,
            chat_id=chat_id,
        ).prefetch_related("message_content")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(ArtifactSummaryResponse(page, many=True).data)
