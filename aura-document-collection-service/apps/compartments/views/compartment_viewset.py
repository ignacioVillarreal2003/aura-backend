from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.compartments.models import Compartment
from apps.compartments.serializers.request import CreateCompartmentRequest, PatchCompartmentRequest
from apps.compartments.serializers.response import CompartmentResponse
from apps.compartments.services import compartment_service
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
        tags=["Compartments"],
        summary="List compartments",
        responses={200: CompartmentResponse(many=True), **_ERR_LIST},
    ),
    create=extend_schema(
        tags=["Compartments"],
        summary="Create compartment",
        request=CreateCompartmentRequest,
        responses={201: CompartmentResponse, **_ERR_WRITE},
    ),
    retrieve=extend_schema(
        tags=["Compartments"],
        summary="Get compartment",
        responses={200: CompartmentResponse, **_ERR_RETRIEVE},
    ),
    partial_update=extend_schema(
        tags=["Compartments"],
        summary="Update compartment",
        request=PatchCompartmentRequest,
        responses={200: CompartmentResponse, **_ERR_WRITE},
    ),
    destroy=extend_schema(
        tags=["Compartments"],
        summary="Delete compartment",
        responses={204: OpenApiResponse(description="No content"), **_ERR_DESTROY},
    ),
)
class CompartmentViewSet(GenericViewSet):
    queryset = Compartment.objects.none()
    pagination_class = StandardPagination
    filter_backends = [OrderingFilter]
    ordering_fields = ["id", "name"]
    ordering = ["name"]
    lookup_value_regex = r"[1-9][0-9]*"

    def list(self, request: Request) -> Response:
        qs = compartment_service.list_compartments(request.user)
        qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(CompartmentResponse(page, many=True).data)

    def create(self, request: Request) -> Response:
        serializer = CreateCompartmentRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = compartment_service.create_compartment(
            request.user,
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
        )
        return Response(CompartmentResponse(obj).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        obj = compartment_service.get_compartment(request.user, int(pk))
        return Response(CompartmentResponse(obj).data)

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        serializer = PatchCompartmentRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = compartment_service.update_compartment(
            request.user,
            int(pk),
            **serializer.validated_data,
        )
        return Response(CompartmentResponse(obj).data)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        compartment_service.delete_compartment(request.user, int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
