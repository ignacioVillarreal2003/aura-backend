from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

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
    auth=[
        {"bearerAuth": []},
        {"serviceApiKey": [], "serviceUserId": [], "serviceUserEmail": []},
    ],
)
@extend_schema_view(
    list=extend_schema(
        tags=["ClassificationLevels"],
        summary="List classification levels",
        responses={200: ClassificationLevelResponse(many=True), **_ERR_LIST},
    ),
    create=extend_schema(
        tags=["ClassificationLevels"],
        summary="Create classification level",
        request=CreateClassificationLevelRequest,
        responses={201: ClassificationLevelResponse, **_ERR_WRITE},
    ),
    retrieve=extend_schema(
        tags=["ClassificationLevels"],
        summary="Get classification level",
        responses={200: ClassificationLevelResponse, **_ERR_RETRIEVE},
    ),
    partial_update=extend_schema(
        tags=["ClassificationLevels"],
        summary="Update classification level",
        request=PatchClassificationLevelRequest,
        responses={200: ClassificationLevelResponse, **_ERR_WRITE},
    ),
    destroy=extend_schema(
        tags=["ClassificationLevels"],
        summary="Delete classification level",
        responses={204: OpenApiResponse(description="No content"), **_ERR_DESTROY},
    ),
)
class ClassificationLevelViewSet(GenericViewSet):
    queryset = ClassificationLevel.objects.none()
    pagination_class = StandardPagination
    filter_backends = [OrderingFilter]
    ordering_fields = ["id", "name", "rank"]
    ordering = ["rank"]
    lookup_value_regex = r"[1-9][0-9]*"

    def list(self, request: Request) -> Response:
        qs = classification_level_service.list_classification_levels(request.user)
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
