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
    StartChatResponse,
    UpdateAssistantRequest,
)
from apps.assistant.services.assistant_service import assistant_service
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
    description="ID del asistente.",
)


class AssistantListCreateView(APIView):

    @extend_schema(
        tags=["Assistants"],
        summary="Listar asistentes activos",
        description="Devuelve los asistentes disponibles para los usuarios. No expone el system prompt.",
        responses={
            200: AssistantUserResponse(many=True),
            **standard_error_responses(401),
        },
    )
    def get(self, request: Request) -> Response:
        AccessControl.require_permissions(request.user, frozenset({perms.LIST_ASSISTANTS}))
        queryset = assistant_service.list_active_assistants(user=request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(AssistantUserResponse(page, many=True).data)

    @extend_schema(
        tags=["Assistants"],
        summary="Crear asistente",
        description=(
            "Crea un nuevo asistente especializado. Requiere permiso `CREATE_ASSISTANT`. "
            "El `system_prompt` es la instrucción fija que el LLM usará en cada sesión."
        ),
        request=CreateAssistantRequest,
        responses={
            201: AssistantAdminResponse,
            **standard_error_responses(400, 401, 403),
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
        responses={
            200: AssistantAdminResponse(many=True),
            **standard_error_responses(401, 403),
        },
    )
    def get(self, request: Request) -> Response:
        AccessControl.require_permissions(request.user, frozenset({perms.MANAGE_ASSISTANTS}))
        queryset = assistant_service.list_all_assistants(user=request.user)
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
            **standard_error_responses(401, 404),
        },
    )
    def get(self, request: Request, assistant_id: int) -> Response:
        assistant = assistant_service.get_assistant(user=request.user, assistant_id=assistant_id)
        return Response(AssistantUserResponse(assistant).data)

    @extend_schema(
        tags=["Assistants"],
        summary="Actualizar asistente",
        description="Actualiza uno o más campos del asistente. Requiere permiso `UPDATE_ASSISTANT`.",
        parameters=[_ID_PARAM],
        request=UpdateAssistantRequest,
        responses={
            200: AssistantAdminResponse,
            **standard_error_responses(400, 401, 403, 404),
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
        summary="Iniciar sesión con asistente",
        description=(
            "Crea un nuevo chat pre-configurado con el system prompt del asistente. "
            "El usuario es añadido automáticamente como propietario del chat. "
            "Devuelve el `chat_id` para navegar a la sesión."
        ),
        parameters=[_ID_PARAM],
        responses={
            201: StartChatResponse,
            **standard_error_responses(401, 403, 404),
        },
    )
    def post(self, request: Request, assistant_id: int) -> Response:
        chat = assistant_service.start_chat(user=request.user, assistant_id=assistant_id)
        return Response(
            {"chat_id": chat.id, "chat_name": chat.name},
            status=status.HTTP_201_CREATED,
        )
