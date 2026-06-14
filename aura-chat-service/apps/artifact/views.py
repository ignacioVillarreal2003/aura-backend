import logging
from datetime import datetime
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.artifact.registry import ARTIFACT_TYPES
from apps.artifact.serializers import (
    ArtifactListResponse,
    ArtifactResponse,
    ArtifactSummaryResponse,
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
_CREATED_BY_PARAM = OpenApiParameter(
    name="created_by",
    type=int,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Filtrar por ID del creador.",
)
_DATE_FROM_PARAM = OpenApiParameter(
    name="date_from",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Fecha de inicio (ISO 8601, ej: 2024-01-01T00:00:00Z).",
)
_DATE_TO_PARAM = OpenApiParameter(
    name="date_to",
    type=str,
    location=OpenApiParameter.QUERY,
    required=False,
    description="Fecha de fin (ISO 8601, ej: 2024-12-31T23:59:59Z).",
)
_CHAT_PATH_PARAM = OpenApiParameter(
    name="chat_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del chat.",
)
_ID_PARAM = OpenApiParameter(
    name="artifact_id",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description="ID del artefacto.",
)

_FEED_PARAMS = [_TYPE_PARAM, _CREATED_BY_PARAM, _DATE_FROM_PARAM, _DATE_TO_PARAM]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone as tz
    dt = parse_datetime(value)
    if dt is None:
        raise ValidationError({"detail": f"Fecha inválida: '{value}'. Usar formato ISO 8601."})
    if dt.tzinfo is None:
        dt = tz.make_aware(dt)
    return dt


def _parse_feed_filters(request: Request) -> dict:
    artifact_type = request.query_params.get("type") or None
    created_by_raw = request.query_params.get("created_by")
    created_by = int(created_by_raw) if created_by_raw and created_by_raw.isdigit() else None
    date_from = _parse_datetime(request.query_params.get("date_from"))
    date_to = _parse_datetime(request.query_params.get("date_to"))
    return {"artifact_type": artifact_type, "created_by": created_by, "date_from": date_from, "date_to": date_to}


class ChatArtifactFeedView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Feed de artefactos del chat",
        description=(
                "Devuelve todos los artefactos del chat paginados, del más reciente al más antiguo. "
                "El usuario debe ser miembro activo del chat. "
                "Filtrable por tipo, creador y rango de fechas."
        ),
        parameters=[_CHAT_PATH_PARAM, *_FEED_PARAMS],
        responses={200: ArtifactSummaryResponse(many=True), **standard_error_responses(400, 401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        filters = _parse_feed_filters(request)
        queryset = artifact_service.list_chat_artifacts(user=request.user, chat_id=chat_id, **filters)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ArtifactSummaryResponse(page, many=True, context={'request': request}).data)


class ChatArtifactManageView(APIView):
    @extend_schema(
        tags=["Artifacts"],
        summary="Feed de artefactos del chat (admin)",
        description=(
                "Lista todos los artefactos del chat sin requerir membresía activa. "
                "No verifica ownership ni pertenencia al chat. "
                "Requiere permiso `MANAGE_CHAT_ARTIFACTS`. "
                "Resultados del más reciente al más antiguo. "
                "Filtrable por tipo, creador y rango de fechas."
        ),
        parameters=[_CHAT_PATH_PARAM, *_FEED_PARAMS],
        responses={200: ArtifactSummaryResponse(many=True), **standard_error_responses(400, 401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        filters = _parse_feed_filters(request)
        queryset = artifact_service.list_chat_artifacts_admin(user=request.user, chat_id=chat_id, **filters)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(ArtifactSummaryResponse(page, many=True, context={'request': request}).data)


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
        summary="Eliminar artefacto",
        description="Elimina suavemente el artefacto. Solo el creador o un miembro activo con rol owner/editor del chat de origen.",
        parameters=[_ID_PARAM],
        responses={204: OpenApiResponse(description="Sin contenido"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, artifact_id: int) -> Response:
        artifact_service.delete_artifact(user=request.user, artifact_id=artifact_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
