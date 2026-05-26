from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.classification_levels.filters import ClassificationLevelFilter
from apps.classification_levels.models import ClassificationLevel
from apps.classification_levels.serializers.request import (
    CreateClassificationLevelRequest,
    PatchClassificationLevelRequest,
)
from apps.classification_levels.serializers.response import ClassificationLevelResponse
from apps.classification_levels.services import classification_level_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

_ERR_LIST = standard_error_responses(401, 403)
_ERR_RETRIEVE = standard_error_responses(401, 403, 404)
_ERR_WRITE = standard_error_responses(400, 401, 403, 404)
_ERR_DESTROY = standard_error_responses(401, 403, 404)


@extend_schema(
    auth=[{"bearerAuth": []}],
    description=(
        "Administrative facade for Mandatory Access ladders that pair human readable labels with deterministic `rank` "
        "ordering. Mutation endpoints guard referential integrity and emit informative conflicts rather than orphaned rows."
    ),
)
@extend_schema_view(
    list=extend_schema(
        tags=["ClassificationLevels"],
        summary="Enumerate MAC classification levels",
        description=(
            "Supports icontains `name` lookups plus bounded `rank` windows; ideal bootstrap data for approvals UI. Requires **LIST_CLASSIFICATION_LEVELS**."
        ),
        parameters=[
            OpenApiParameter(
                name="ordering",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Whitelist: `id`, `name`, `rank` — default ascending by `rank` for sane ladder previews.",
                required=False,
            ),
            OpenApiParameter(
                name="name",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Substring match honoring case-insensitivity.",
                required=False,
            ),
            OpenApiParameter(
                name="rank_gte",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Lower inclusive bound filtering `rank`.",
                required=False,
            ),
            OpenApiParameter(
                name="rank_lte",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Upper inclusive bound filtering `rank`.",
                required=False,
            ),
            OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name="page_size", type=int, location=OpenApiParameter.QUERY, required=False),
        ],
        responses={200: ClassificationLevelResponse(many=True), **_ERR_LIST},
    ),
    create=extend_schema(
        tags=["ClassificationLevels"],
        summary="Persist new classification ladder node",
        description=(
            "Duplicate lexical names or conflicting ranks collide with **`duplicate_classification_level`** when business rules disallow them. Requires **CREATE_CLASSIFICATION_LEVEL**."
        ),
        request=CreateClassificationLevelRequest,
        responses={201: ClassificationLevelResponse, **_ERR_WRITE},
    ),
    retrieve=extend_schema(
        tags=["ClassificationLevels"],
        summary="Retrieve classification ladder node",
        description="404 (`classification_level_not_found`) mirrors missing ids or deactivated catalogue entries.",
        responses={200: ClassificationLevelResponse, **_ERR_RETRIEVE},
    ),
    partial_update=extend_schema(
        tags=["ClassificationLevels"],
        summary="Rename or rerank an existing ladder node",
        description=(
            "PATCH semantics minimise accidental wipes—always send subsets. Clearing references already protected by guarded deletes. Requires **UPDATE_CLASSIFICATION_LEVEL**."
        ),
        request=PatchClassificationLevelRequest,
        responses={200: ClassificationLevelResponse, **_ERR_WRITE},
    ),
    destroy=extend_schema(
        tags=["ClassificationLevels"],
        summary="Attempt hard delete with dependency checks",
        description=(
            "Rows still referenced bubble conflicts via **`classification_level_in_use`** to stop silent MAC drift. "
            "**DELETE_CLASSIFICATION_LEVEL** permission required."
        ),
        responses={204: OpenApiResponse(description="No body when removal succeeds."), **_ERR_DESTROY},
    ),
)
class ClassificationLevelViewSet(GenericViewSet):
    queryset = ClassificationLevel.objects.none()
    pagination_class = StandardPagination
    filterset_class = ClassificationLevelFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["id", "name", "rank"]
    ordering = ["rank"]
    lookup_value_regex = r"[1-9][0-9]*"

    def list(self, request: Request) -> Response:
        qs = classification_level_service.list_classification_levels(request.user)
        if isinstance(qs, QuerySet):
            qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(ClassificationLevelResponse(page, many=True).data)

    def create(self, request: Request) -> Response:
        serializer = CreateClassificationLevelRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = classification_level_service.create_classification_level(
            request.user,
            name=serializer.validated_data["name"],
            rank=serializer.validated_data["rank"],
            description=serializer.validated_data.get("description", ""),
        )
        return Response(ClassificationLevelResponse(obj).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        obj = classification_level_service.get_classification_level(request.user, int(pk))
        return Response(ClassificationLevelResponse(obj).data)

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        serializer = PatchClassificationLevelRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = classification_level_service.update_classification_level(
            request.user,
            int(pk),
            **serializer.validated_data,
        )
        return Response(ClassificationLevelResponse(obj).data)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        classification_level_service.delete_classification_level(request.user, int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
