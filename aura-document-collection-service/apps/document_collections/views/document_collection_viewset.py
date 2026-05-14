from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.document_collections.filters import DocumentCollectionFilter
from apps.document_collections.models import DocumentCollection
from apps.document_collections.serializers.request import (
    CreateDocumentCollectionRequest,
    PatchDocumentCollectionRequest,
)
from apps.document_collections.serializers.response import DocumentCollectionResponse
from apps.document_collections.services.document_collection_service import (
    document_collection_service,
)
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

_ERR_LIST = standard_error_responses(401, 403)
_ERR_RETRIEVE = standard_error_responses(401, 403, 404)
_ERR_WRITE = standard_error_responses(400, 401, 403, 404)
_ERR_DESTROY = standard_error_responses(401, 403, 404)

_ORDERING_HINT = OpenApiParameter(
    name="ordering",
    type=str,
    location=OpenApiParameter.QUERY,
    description=(
        "Comma-separated field(s) respecting DRF OrderingFilter semantics. Prefix with `-` for descending. "
        "Allowed: `id`, `name`, `created_at`, `updated_at`; default `-created_at`."
    ),
    required=False,
)


@extend_schema(
    auth=[{"bearerAuth": []}],
    description=(
        "Manage logical groupings tying external document ids together under Mandatory Access Control primitives. "
        "Deletes intentionally **soft-remove** audits while reads honour active markers only via repository queries."
    ),
)
@extend_schema_view(
    list=extend_schema(
        tags=["DocumentCollections"],
        summary="List MAC-aware document collections",
        description=(
            "Returns paginated, filterable inventories of collections including nested classification/compartment slices. "
            "Requires **LIST_DOCUMENT_COLLECTIONS** capability."
        ),
        parameters=[
            _ORDERING_HINT,
            OpenApiParameter(
                name="name",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Case-insensitive substring match against `document_collection.name`.",
                required=False,
            ),
            OpenApiParameter(
                name="created_by",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Exact match filtering on authoring user id persisted at insertion.",
                required=False,
            ),
            OpenApiParameter(
                name="created_after",
                type=str,
                location=OpenApiParameter.QUERY,
                description="ISO-8601 lower bound inclusive on `created_at`.",
                required=False,
            ),
            OpenApiParameter(
                name="created_before",
                type=str,
                location=OpenApiParameter.QUERY,
                description="ISO-8601 upper bound inclusive on `created_at`.",
                required=False,
            ),
            OpenApiParameter(
                name="page",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Page number for standard pagination.",
                required=False,
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Optional override capped at StandardPagination.MAX limit (defaults to configured page size).",
                required=False,
            ),
        ],
        responses={200: DocumentCollectionResponse(many=True), **_ERR_LIST},
    ),
    create=extend_schema(
        tags=["DocumentCollections"],
        summary="Create collection with clearance + compartments",
        description=(
            "Atomically allocates a DocumentCollection pivoting on `classification_level_id` and rewires compartment "
            "memberships. Requires **CREATE_DOCUMENT_COLLECTION** and validates existence of FK targets."
        ),
        request=CreateDocumentCollectionRequest,
        responses={201: DocumentCollectionResponse, **_ERR_WRITE},
    ),
    retrieve=extend_schema(
        tags=["DocumentCollections"],
        summary="Retrieve a single collection by id",
        description=(
            "Hydrates catalogue joins for readability. Missing/soft deleted rows bubble up as **`document_collection_not_found`**."
        ),
        responses={200: DocumentCollectionResponse, **_ERR_RETRIEVE},
    ),
    partial_update=extend_schema(
        tags=["DocumentCollections"],
        summary="PATCH mutable collection facets",
        description=(
            "`PATCH`-only ergonomics—send sparse JSON. Updating `compartment_ids` rewires memberships atomically "
            "(non-empty replacements). Requires **UPDATE_DOCUMENT_COLLECTION**."
        ),
        request=PatchDocumentCollectionRequest,
        responses={200: DocumentCollectionResponse, **_ERR_WRITE},
    ),
    destroy=extend_schema(
        tags=["DocumentCollections"],
        summary="Soft-delete a collection row",
        description=(
            "`DELETE` logically retires collections while retaining historical provenance (**soft delete**) so audit pipelines "
            "remain intact. Requires **DELETE_DOCUMENT_COLLECTION**."
        ),
        responses={204: OpenApiResponse(description="No body on success."), **_ERR_DESTROY},
    ),
)
class DocumentCollectionViewSet(GenericViewSet):
    queryset = DocumentCollection.objects.none()
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = DocumentCollectionFilter
    ordering_fields = ["id", "name", "created_at", "updated_at"]
    ordering = ["-created_at"]
    lookup_value_regex = r"[1-9][0-9]*"

    def list(self, request: Request) -> Response:
        qs = document_collection_service.list_document_collections(request.user)
        if isinstance(qs, QuerySet):
            qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(DocumentCollectionResponse(page, many=True).data)

    def create(self, request: Request) -> Response:
        serializer = CreateDocumentCollectionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_collection = document_collection_service.create_document_collection(
            request.user,
            name=serializer.validated_data["name"],
            classification_level_id=serializer.validated_data["classification_level_id"],
            compartment_ids=serializer.validated_data["compartment_ids"],
        )
        return Response(DocumentCollectionResponse(document_collection).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        document_collection = document_collection_service.get_document_collection(request.user, int(pk))
        return Response(DocumentCollectionResponse(document_collection).data)

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        serializer = PatchDocumentCollectionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_collection = document_collection_service.update_document_collection(
            request.user,
            int(pk),
            name=serializer.validated_data.get("name"),
            classification_level_id=serializer.validated_data.get("classification_level_id"),
            compartment_ids=serializer.validated_data.get("compartment_ids"),
        )
        return Response(DocumentCollectionResponse(document_collection).data)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        document_collection_service.delete_document_collection(request.user, int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
