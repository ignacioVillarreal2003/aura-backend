import logging
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.assistant.serializers import (
    AssistantAdminResponse,
    AssistantUserResponse,
    CreateAssistantRequest,
    StartChatRequest,
    StartChatResponse,
    UpdateAssistantRequest,
)
from apps.assistant.services.assistant_service import assistant_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_ID_PARAM = OpenApiParameter(
    name="assistant_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del asistente.",
)
_SEARCH_PARAM = OpenApiParameter(
    name="search",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Filtrar por nombre (case-insensitive contains).",
)


class AssistantListCreateView(APIView):
    @extend_schema(
        tags=["Assistants"],
        summary="Listar asistentes activos",
        description="Devuelve los asistentes disponibles para los usuarios. No expone el system prompt.",
        parameters=[_SEARCH_PARAM],
        responses={
            200: AssistantUserResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        search = request.query_params.get("search") or None
        queryset = assistant_service.list_active_assistants(user=request.user, search=search)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AssistantUserResponse(page, many=True).data)

    @extend_schema(
        tags=["Assistants"],
        summary="Crear asistente",
        description=(
                "Crea un nuevo asistente especializado. Requiere permiso `CREATE_ASSISTANT`. "
                "El `system_prompt` es la instrucción fija que el LLM usará en cada sesión. "
                "El nombre debe ser único entre asistentes activos."
        ),
        request=CreateAssistantRequest,
        responses={
            201: AssistantAdminResponse,
            **standard_error_responses(400, 401, 403, 409),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = CreateAssistantRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        assistant = assistant_service.create_assistant(
            user=request.user,
            name=d["name"],
            description=d.get("description", ""),
            system_prompt=d["system_prompt"],
            response_style=d.get("response_style", ""),
            avatar_emoji=d.get("avatar_emoji", ""),
            is_active=d.get("is_active", True),
        )
        return Response(AssistantAdminResponse(assistant).data, status=status.HTTP_201_CREATED)


class AssistantManageView(APIView):
    @extend_schema(
        tags=["Assistants"],
        summary="Listar todos los asistentes (admin)",
        description=(
                "Lista todos los asistentes incluyendo los inactivos. "
                "Incluye el system_prompt. Requiere permiso `MANAGE_ASSISTANTS`."
        ),
        parameters=[_SEARCH_PARAM],
        responses={
            200: AssistantAdminResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        search = request.query_params.get("search") or None
        queryset = assistant_service.list_all_assistants(user=request.user, search=search)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AssistantAdminResponse(page, many=True).data)


class AssistantDetailView(APIView):
    @extend_schema(
        tags=["Assistants"],
        summary="Obtener asistente",
        description="Devuelve el detalle del asistente sin exponer el system prompt.",
        parameters=[_ID_PARAM],
        responses={
            200: AssistantUserResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def get(self, request: Request, assistant_id: int) -> Response:
        assistant = assistant_service.get_assistant(user=request.user, assistant_id=assistant_id)
        return Response(AssistantUserResponse(assistant).data)

    @extend_schema(
        tags=["Assistants"],
        summary="Actualizar asistente",
        description=(
                "Actualiza uno o más campos del asistente. Requiere permiso `UPDATE_ASSISTANT`. "
                "Si se cambia el nombre, debe ser único entre asistentes activos."
        ),
        parameters=[_ID_PARAM],
        request=UpdateAssistantRequest,
        responses={
            200: AssistantAdminResponse,
            **standard_error_responses(400, 401, 403, 404, 409),
        },
    )
    def patch(self, request: Request, assistant_id: int) -> Response:
        serializer = UpdateAssistantRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        assistant = assistant_service.update_assistant(
            user=request.user,
            assistant_id=assistant_id,
            name=d.get("name"),
            description=d.get("description"),
            system_prompt=d.get("system_prompt"),
            response_style=d.get("response_style"),
            avatar_emoji=d.get("avatar_emoji"),
            is_active=d.get("is_active"),
        )
        return Response(AssistantAdminResponse(assistant).data)

    @extend_schema(
        tags=["Assistants"],
        summary="Eliminar asistente",
        description="Eliminación suave del asistente. Requiere permiso `DELETE_ASSISTANT`.",
        parameters=[_ID_PARAM],
        responses={
            204: OpenApiResponse(description="Sin contenido"),
            **standard_error_responses(401, 403, 404),
        },
    )
    def delete(self, request: Request, assistant_id: int) -> Response:
        assistant_service.delete_assistant(user=request.user, assistant_id=assistant_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssistantStartChatView(APIView):
    @extend_schema(
        tags=["Assistants"],
        summary="Iniciar o reanudar sesión con asistente",
        description=(
                "Si `resume=false` (default): crea siempre un chat nuevo pre-configurado con el system prompt "
                "del asistente y añade al usuario como propietario. "
                "Si `resume=true`: devuelve el chat más reciente del usuario con este asistente si existe "
                "(HTTP 200), o crea uno nuevo si no hay ninguno (HTTP 201). "
                "La respuesta incluye `is_new` para distinguir ambos casos."
        ),
        parameters=[_ID_PARAM],
        request=StartChatRequest,
        responses={
            200: StartChatResponse,
            201: StartChatResponse,
            **standard_error_responses(400, 401, 403, 404),
        },
    )
    def post(self, request: Request, assistant_id: int) -> Response:
        serializer = StartChatRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        chat, is_new = assistant_service.start_chat(
            user=request.user,
            assistant_id=assistant_id,
            resume=serializer.validated_data.get("resume", False),
        )
        return Response(
            StartChatResponse({"chat_id": chat.id, "chat_name": chat.name, "is_new": is_new}).data,
            status=status.HTTP_201_CREATED if is_new else status.HTTP_200_OK,
        )
