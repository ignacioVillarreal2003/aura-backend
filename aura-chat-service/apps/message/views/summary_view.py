from asgiref.sync import async_to_sync
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.message.exceptions import LLMServiceException
from apps.message.serializers.response import MessageResponse
from apps.message.services.message_service import message_service
from core.openapi.common import standard_error_responses


class SummaryRequestSerializer(serializers.Serializer):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=50,
        help_text="IDs de los documentos a resumir (mínimo 1, máximo 50).",
    )


class DocumentSummaryView(APIView):

    @extend_schema(
        tags=["Messages"],
        summary="Resumir documentos del chat",
        description=(
            "Genera un resumen de los documentos indicados llamando al servicio LLM y "
            "persiste el resultado como mensaje del asistente en el chat."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request=SummaryRequestSerializer,
        responses={
            201: inline_serializer(
                name="DocumentSummaryResponse",
                fields={
                    "message": MessageResponse(),
                    "summary": serializers.CharField(),
                    "fragments": serializers.ListField(child=serializers.DictField()),
                },
            ),
            **standard_error_responses(400, 401, 403, 404, 502),
        },
    )
    def post(self, request: Request, chat_id: int) -> Response:
        return async_to_sync(self._post_async)(request, chat_id)

    async def _post_async(self, request: Request, chat_id: int) -> Response:
        serializer = SummaryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_ids: list[int] = serializer.validated_data["document_ids"]

        result = await message_service.run_document_summary(
            user=request.user,
            chat_id=chat_id,
            document_ids=document_ids,
        )

        body = {
            "message": MessageResponse(result.assistant_message).data if result.assistant_message else None,
            "summary": result.summary,
            "fragments": result.fragments,
        }
        return Response(body, status=status.HTTP_201_CREATED)
