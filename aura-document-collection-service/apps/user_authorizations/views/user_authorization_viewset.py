from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.document_collection_documents.serializers.response import AccessibleDocumentResponse
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

_AUTH = [{"bearerAuth": []}]

_TARGET_USER = OpenApiParameter(
    name="user_id",
    type=int,
    location=OpenApiParameter.PATH,
    description="Numeric ID of the user whose MAC profile (clearance + compartments) is being read or modified.",
)


@extend_schema(
    tags=["UserAuthorizations"],
    auth=_AUTH,
    description=(
        "Operational surface manipulating **per-user MAC profiles**: aggregated snapshots, clearance upserts/removals, compartment grants, "
        "and authoritative listings of **`DocumentCollection`** objects the intersection algorithm unlocks (`accessible-collections`)."
    ),
)
class UserAuthorizationViewSet(GenericViewSet):
    queryset = []
    pagination_class = StandardPagination
    filter_backends = [OrderingFilter]
    lookup_field = "user_id"
    lookup_value_regex = r"[1-9][0-9]*"

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="Hydrate aggregated MAC snapshot",
        description=(
            "Bundles optional clearance (`user_clearance`) with every **`user_compartment`** membership currently active—handy ahead of "
            "issuing deltas or illustrating UI dashboards."
        ),
        auth=_AUTH,
        parameters=[_TARGET_USER],
        responses={200: UserAuthorizationResponse, **_ERR_BASE},
    )
    def retrieve(self, request: Request, user_id: str | None = None) -> Response:
        data = user_authorization_service.get_user_authorization(request.user, int(user_id))
        return Response(UserAuthorizationResponse(data).data)

    @extend_schema(
        methods=["put"],
        tags=["UserAuthorizations"],
        summary="Upsert Mandatory Access clearance ceiling",
        description=(
            "`PUT /clearance/` overwrites whichever clearance row existed (single-row cardinality per user). Missing classification levels propagate **`classification_level_not_found`**. "
            "**SET_USER_CLEARANCE** permission compulsory."
        ),
        auth=_AUTH,
        parameters=[_TARGET_USER],
        request=SetUserClearanceRequest,
        responses={200: UserClearanceResponse, **_ERR_WRITE},
    )
    @extend_schema(
        methods=["delete"],
        tags=["UserAuthorizations"],
        summary="Revoke clearance if present",
        description=(
            "**204** empties semantics when succeeds; **`user_clearance_not_found`** (404-equivalent envelope) communicates nothing-to-delete scenarios so scripts stay idempotent-friendly."
        ),
        auth=_AUTH,
        parameters=[_TARGET_USER],
        responses={204: OpenApiResponse(description="Clears clearance without response body."), **_ERR_BASE},
    )
    @action(detail=True, methods=["put", "delete"], url_path="clearance", url_name="clearance")
    def clearance(self, request: Request, user_id: str | None = None) -> Response:
        if request.method == "DELETE":
            user_authorization_service.delete_user_clearance(request.user, int(user_id))
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = SetUserClearanceRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = user_authorization_service.set_user_clearance(
            request.user,
            int(user_id),
            classification_level_id=serializer.validated_data["classification_level_id"],
        )
        return Response(UserClearanceResponse(result).data)
        if request.method == "PUT":
            serializer = SetUserClearanceRequest(data=request.data)
            serializer.is_valid(raise_exception=True)
            clearance = user_authorization_service.set_user_clearance(
                request.user,
                int(user_id),
                classification_level_id=serializer.validated_data["classification_level_id"],
            )
            return Response(UserClearanceResponse(clearance).data)
        user_authorization_service.delete_user_clearance(request.user, int(user_id))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        methods=["get"],
        tags=["UserAuthorizations"],
        summary="Enumerate compartment memberships",
        description=(
            "Standard pagination applies because power users might accumulate dozens of compartments. Requires **LIST_USER_COMPARTMENTS**."
        ),
        auth=_AUTH,
        parameters=[
            _TARGET_USER,
            OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name="page_size", type=int, location=OpenApiParameter.QUERY, required=False),
        ],
        responses={200: UserCompartmentResponse(many=True), **_ERR_BASE},
    )
    @extend_schema(
        methods=["post"],
        tags=["UserAuthorizations"],
        summary="Grant compartment membership",
        description=(
            "**201** echoes the hydrated membership join. Duplicate attempts raise **`duplicate_user_compartment`** (HTTP 409) so automation can branch cleanly. Requires **ADD_USER_COMPARTMENT**."
        ),
        auth=_AUTH,
        parameters=[_TARGET_USER],
        request=AddUserCompartmentRequest,
        responses={201: UserCompartmentResponse, **_ERR_CONFLICT},
    )
    @action(detail=True, methods=["get", "post"], url_path="compartments", url_name="compartments")
    def compartments(self, request: Request, user_id: str | None = None) -> Response:
        if request.method == "GET":
            qs = user_authorization_service.list_user_compartments(request.user, int(user_id))
            page = self.paginate_queryset(qs)
            return self.get_paginated_response(UserCompartmentResponse(page, many=True).data)
        serializer = AddUserCompartmentRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = user_authorization_service.add_user_compartment(
            request.user,
            int(user_id),
            compartment_id=serializer.validated_data["compartment_id"],
        )
        return Response(UserCompartmentResponse(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="Revoke compartment membership",
        auth=_AUTH,
        parameters=[
            _TARGET_USER,
            OpenApiParameter(
                name="compartment_id",
                location=OpenApiParameter.PATH,
                type=int,
                description="Explicit compartment surrogate key detached from `{user}` in this DELETE operation.",
                required=True,
            ),
        ],
        responses={204: OpenApiResponse(description="Successful removal returns no payload."), **_ERR_BASE},
        description=(
            "Path nests `compartments/{compartment_id}` for clarity. **`user_compartment_not_found`** distinguishes "
            "missing memberships from generic not-found semantics."
        ),
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
        user_id: str | None = None,
        compartment_id: str | None = None,
    ) -> Response:
        user_authorization_service.remove_user_compartment(
            request.user,
            int(user_id),
            compartment_id=int(compartment_id),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="Intersect clearance + compartments to discover accessible collections",
        description=(
            "Primary integration hook for federated microservices: returns **`DocumentCollection`** payloads (same serializers as catalogue routes) constrained by MAC intersections. Pagination mirrors other list endpoints "
            "so caching layers can prefetch windows of accessible work queues. Requires **GET_USER_ACCESSIBLE_COLLECTIONS**."
        ),
        auth=_AUTH,
        parameters=[
            _TARGET_USER,
            OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name="page_size", type=int, location=OpenApiParameter.QUERY, required=False),
        ],
        responses={200: DocumentCollectionResponse(many=True), **_ERR_BASE},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="accessible-collections",
        url_name="accessible-collections",
    )
    def accessible_collections(self, request: Request, user_id: str | None = None) -> Response:
        qs = user_authorization_service.get_accessible_collections(request.user, int(user_id))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(DocumentCollectionResponse(page, many=True).data)

    @extend_schema(
        tags=["UserAuthorizations"],
        summary="List all documents accessible to a user across their permitted collections",
        description=(
            "Applies the full MAC intersection (clearance rank + compartment membership) to resolve every "
            "collection the user can access, then returns every active document linked to those collections. "
            "A document linked to more than one accessible collection appears once per collection so callers "
            "retain full provenance. Pagination mirrors other list endpoints. "
            "Requires **GET_USER_ACCESSIBLE_DOCUMENTS**."
        ),
        auth=_AUTH,
        parameters=[
            _TARGET_USER,
            OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name="page_size", type=int, location=OpenApiParameter.QUERY, required=False),
        ],
        responses={200: AccessibleDocumentResponse(many=True), **_ERR_BASE},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="accessible-documents",
        url_name="accessible-documents",
    )
    def accessible_documents(self, request: Request, user_id: str | None = None) -> Response:
        qs = user_authorization_service.get_accessible_documents(request.user, int(user_id))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(AccessibleDocumentResponse(page, many=True).data)
