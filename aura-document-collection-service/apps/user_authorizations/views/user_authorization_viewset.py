from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.document_collections.serializers.response import DocumentCollectionResponse
from apps.user_authorizations.serializers.request import (
    AddUserCompartmentRequest,
    SetUserClearanceRequest,
)
from apps.user_authorizations.serializers.response import (
    UserAuthorizationResponse,
    UserClearanceResponse,
    UserCompartmentResponse,
)
from apps.user_authorizations.services import user_authorization_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

_ERR_BASE = standard_error_responses(401, 403, 404)
_ERR_WRITE = standard_error_responses(400, 401, 403, 404)
_ERR_CONFLICT = standard_error_responses(400, 401, 403, 404, 409)

_AUTH = [
    {"bearerAuth": []},
    {"serviceApiKey": [], "serviceUserId": [], "serviceUserEmail": []},
]


class UserAuthorizationViewSet(GenericViewSet):
    queryset = []
    pagination_class = StandardPagination
    filter_backends = [OrderingFilter]
    lookup_value_regex = r"[1-9][0-9]*"

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="Get user authorization summary",
        auth=_AUTH,
        responses={200: UserAuthorizationResponse, **_ERR_BASE},
    )
    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        data = user_authorization_service.get_user_authorization(request.user, int(pk))
        return Response(UserAuthorizationResponse(data).data)

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="Set user clearance level",
        auth=_AUTH,
        request=SetUserClearanceRequest,
        responses={200: UserClearanceResponse, **_ERR_WRITE},
    )
    @action(detail=True, methods=["put"], url_path="clearance", url_name="set-clearance")
    def set_clearance(self, request: Request, pk: str | None = None) -> Response:
        serializer = SetUserClearanceRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        clearance = user_authorization_service.set_user_clearance(
            request.user,
            int(pk),
            classification_level_id=serializer.validated_data["classification_level_id"],
        )
        return Response(UserClearanceResponse(clearance).data)

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="Delete user clearance",
        auth=_AUTH,
        responses={204: OpenApiResponse(description="No content"), **_ERR_BASE},
    )
    @action(detail=True, methods=["delete"], url_path="clearance", url_name="delete-clearance")
    def delete_clearance(self, request: Request, pk: str | None = None) -> Response:
        user_authorization_service.delete_user_clearance(request.user, int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="List user compartments",
        auth=_AUTH,
        responses={200: UserCompartmentResponse(many=True), **_ERR_BASE},
    )
    @action(detail=True, methods=["get"], url_path="compartments", url_name="list-compartments")
    def list_compartments(self, request: Request, pk: str | None = None) -> Response:
        qs = user_authorization_service.list_user_compartments(request.user, int(pk))
        page = self.paginate_queryset(list(qs))
        return self.get_paginated_response(UserCompartmentResponse(page, many=True).data)

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="Add compartment to user",
        auth=_AUTH,
        request=AddUserCompartmentRequest,
        responses={201: UserCompartmentResponse, **_ERR_CONFLICT},
    )
    @action(detail=True, methods=["post"], url_path="compartments", url_name="add-compartment")
    def add_compartment(self, request: Request, pk: str | None = None) -> Response:
        serializer = AddUserCompartmentRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = user_authorization_service.add_user_compartment(
            request.user,
            int(pk),
            compartment_id=serializer.validated_data["compartment_id"],
        )
        return Response(UserCompartmentResponse(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="Remove compartment from user",
        auth=_AUTH,
        parameters=[
            OpenApiParameter(
                name="compartment_id",
                location=OpenApiParameter.PATH,
                type=int,
                description="Compartment ID to remove",
            )
        ],
        responses={204: OpenApiResponse(description="No content"), **_ERR_BASE},
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"compartments/(?P<compartment_id>[1-9][0-9]*)",
        url_name="remove-compartment",
    )
    def remove_compartment(
        self,
        request: Request,
        pk: str | None = None,
        compartment_id: str | None = None,
    ) -> Response:
        user_authorization_service.remove_user_compartment(
            request.user,
            int(pk),
            compartment_id=int(compartment_id),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="Get collections accessible to user (MAC check)",
        description=(
            "Returns all document collections the user can access based on their clearance level "
            "and compartment memberships. Used by other microservices to enforce MAC at the document layer."
        ),
        auth=_AUTH,
        responses={200: DocumentCollectionResponse(many=True), **_ERR_BASE},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="accessible-collections",
        url_name="accessible-collections",
    )
    def accessible_collections(self, request: Request, pk: str | None = None) -> Response:
        qs = user_authorization_service.get_accessible_collections(request.user, int(pk))
        page = self.paginate_queryset(list(qs))
        return self.get_paginated_response(DocumentCollectionResponse(page, many=True).data)
