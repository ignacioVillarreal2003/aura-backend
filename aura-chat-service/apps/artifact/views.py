import logging
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact.registry import ARTIFACT_TYPES
from apps.artifact.serializers import (
    ArtifactListResponse,
    ArtifactResponse,
    ArtifactVersionResponse,
    CreateArtifactRequest,
    UpdateArtifactRequest,
)
from apps.artifact.services.artifact_service import artifact_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

logger = logging.getLogger(__name__)

_TYPE_PARAM = OpenApiParameter(
    name="type",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    enum=sorted(ARTIFACT_TYPES),
    description="Filtrar por tipo de artefacto.",
)
_CHAT_FILTER_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Filtrar por chat de origen. El usuario debe ser miembro activo del chat.",
)
_ID_PARAM = OpenApiParameter(
    name="artifact_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del artefacto.",
)


class ArtifactListView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Listar artefactos",
        description="Devuelve los artefactos del usuario autenticado, paginados. Filtrable por tipo y por chat de origen.",
        parameters=[_TYPE_PARAM, _CHAT_FILTER_PARAM],
        responses={200: ArtifactListResponse(many=True), **standard_error_responses(400, 401, 403, 404)},
    )
    def get(self, request: Request) -> Response:
        artifact_type = request.query_params.get("type") or None
        chat_id_raw = request.query_params.get("chat_id")
        chat_id = int(chat_id_raw) if chat_id_raw and chat_id_raw.isdigit() else None
        queryset = artifact_service.list_artifacts(
            user=request.user, artifact_type=artifact_type, chat_id=chat_id
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ArtifactListResponse(page, many=True).data)

    @extend_schema(
        tags=["Artifacts"],
        summary="Crear artefacto",
        description="Crea un artefacto (cabecera unificada). Si se pasa `source_chat_id`, el usuario debe ser contribuidor del chat.",
        request=CreateArtifactRequest,
        responses={201: ArtifactResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request) -> Response:
        serializer = CreateArtifactRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        artifact = artifact_service.create_artifact(
            user=request.user,
            type=d["type"],
            title=d["title"],
            description=d.get("description", ""),
            status=d.get("status", "draft"),
            source_chat_id=d.get("source_chat_id"),
        )
        return Response(ArtifactResponse(artifact).data, status=status.HTTP_201_CREATED)


class ArtifactDetailView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Obtener artefacto",
        parameters=[_ID_PARAM],
        responses={200: ArtifactResponse, **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, artifact_id: int) -> Response:
        artifact = artifact_service.get_artifact(user=request.user, artifact_id=artifact_id)
        return Response(ArtifactResponse(artifact).data)

    @extend_schema(
        tags=["Artifacts"],
        summary="Actualizar artefacto",
        description="Actualiza título/descripción/estado. Cada cambio incrementa la versión y agrega una entrada al historial.",
        parameters=[_ID_PARAM],
        request=UpdateArtifactRequest,
        responses={200: ArtifactResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def patch(self, request: Request, artifact_id: int) -> Response:
        serializer = UpdateArtifactRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        artifact = artifact_service.update_artifact(
            user=request.user,
            artifact_id=artifact_id,
            title=d.get("title"),
            description=d.get("description"),
            status=d.get("status"),
            change_summary=d.get("change_summary", ""),
        )
        return Response(ArtifactResponse(artifact).data)

    @extend_schema(
        tags=["Artifacts"],
        summary="Eliminar artefacto",
        description="Elimina suavemente el artefacto. Solo el creador o un miembro activo con rol owner/editor del chat de origen.",
        parameters=[_ID_PARAM],
        responses={204: OpenApiResponse(description="Sin contenido"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, artifact_id: int) -> Response:
        artifact_service.delete_artifact(user=request.user, artifact_id=artifact_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ArtifactVersionsView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Listar versiones de un artefacto",
        parameters=[_ID_PARAM],
        responses={200: ArtifactVersionResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, artifact_id: int) -> Response:
        queryset = artifact_service.list_versions(user=request.user, artifact_id=artifact_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ArtifactVersionResponse(page, many=True).data)


class ArtifactManageView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Listar todos los artefactos (admin)",
        description="Lista los artefactos de todos los usuarios. Requiere permiso `MANAGE_ARTIFACTS`.",
        parameters=[_TYPE_PARAM],
        responses={200: ArtifactListResponse(many=True), **standard_error_responses(400, 401, 403)},
    )
    def get(self, request: Request) -> Response:
        artifact_type = request.query_params.get("type") or None
        queryset = artifact_service.list_all_artifacts(user=request.user, artifact_type=artifact_type)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ArtifactListResponse(page, many=True).data)
