from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.document_collection_documents.filters import DocumentInDocumentCollectionFilter
from apps.document_collection_documents.models import DocumentInDocumentCollection
from apps.document_collection_documents.serializers.request import AddDocumentToDocumentCollectionRequest
from apps.document_collection_documents.serializers.response import DocumentInDocumentCollectionResponse
from apps.document_collection_documents.services.document_collection_document_service import (
    document_collection_document_service,
)
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

_ERR_LIST = standard_error_responses(401, 403, 404)
_ERR_CREATE = standard_error_responses(400, 401, 403, 404, 409)
_ERR_DESTROY = standard_error_responses(401, 403, 404)

_PARENT_COLLECTION = OpenApiParameter(
    name="document_collection_pk",
    type=int,
    location=OpenApiParameter.PATH,
    required=True,
    description=(
        "Positive integer surrogate key referencing the parent `/document-collections/{id}` resource. Presence unlocks nested membership operations."
    ),
)


@extend_schema(
    auth=[{"bearerAuth": []}],
    description=(
        "Bridge routes attaching surrogate document ids persisted in **`document`** to owning collections via join rows "
        "`document_in_document_collection`. Responses surface lightweight excerpts rather than heavyweight media payloads."
    ),
)
@extend_schema_view(
    list=extend_schema(
        tags=["DocumentCollectionDocuments"],
        summary="List linked documents inside a collection",
        description=(
            "Paginates join rows honoring filters such as targeted `document_id` or textual search against stored "
            "document descriptors. Requires **LIST_DOCUMENT_COLLECTION_DOCUMENTS** and a valid parent collection id."
        ),
        parameters=[
            _PARENT_COLLECTION,
            OpenApiParameter(
                name="ordering",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Allowed sorts: `id`, `created_at`, `document_id` (defaults ascending by `id`).",
                required=False,
            ),
            OpenApiParameter(
                name="document_id",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Restrict result set to memberships referencing this document surrogate key.",
                required=False,
            ),
            OpenApiParameter(
                name="document_name",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Case-insensitive substring match evaluated against persisted `document.name`.",
                required=False,
            ),
            OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name="page_size", type=int, location=OpenApiParameter.QUERY, required=False),
        ],
        responses={
            200: DocumentInDocumentCollectionResponse(many=True),
            **_ERR_LIST,
        },
    ),
    create=extend_schema(
        tags=["DocumentCollectionDocuments"],
        summary="Link existing document registry entry",
        description=(
            "`POST` idempotently friendly until duplicates appear—Integrity violations become **`duplicate_document_link`** conflicts. Requires **ADD_DOCUMENT_COLLECTION_DOCUMENT**."
        ),
        parameters=[_PARENT_COLLECTION],
        request=AddDocumentToDocumentCollectionRequest,
        responses={
            201: DocumentInDocumentCollectionResponse,
            **_ERR_CREATE,
        },
    ),
    destroy=extend_schema(
        tags=["DocumentCollectionDocuments"],
        summary="Detach document membership by document id",
        description=(
            "Unlinks a document from a collection by the **`document.id`** (the upstream surrogate key), "
            "not the `document_in_document_collection` join-row id. Errors map to **`document_link_not_found`** "
            "when the membership does not exist. Requires **REMOVE_DOCUMENT_COLLECTION_DOCUMENT**."
        ),
        parameters=[
            _PARENT_COLLECTION,
            OpenApiParameter(
                name="pk",
                type=int,
                location=OpenApiParameter.PATH,
                required=True,
                description="The `document.id` surrogate key of the document to unlink from this collection.",
            ),
        ],
        responses={
            204: OpenApiResponse(description="Empty body signalling successful unlink."),
            **_ERR_DESTROY,
        },
    ),
)
class DocumentCollectionDocumentViewSet(GenericViewSet):
    queryset = DocumentInDocumentCollection.objects.none()
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = DocumentInDocumentCollectionFilter
    ordering_fields = ["id", "created_at", "document_id"]
    ordering = ["id"]
    lookup_value_regex = r"[1-9][0-9]*"

    def list(self, request: Request, document_collection_pk: str | None = None) -> Response:
        document_collection_id_int = int(document_collection_pk)
        qs = document_collection_document_service.list_document_collection_documents(
            request.user,
            document_collection_id_int,
        )
        if isinstance(qs, QuerySet):
            qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(
            DocumentInDocumentCollectionResponse(page, many=True).data
        )

    def create(self, request: Request, document_collection_pk: str | None = None) -> Response:
        document_collection_id_int = int(document_collection_pk)
        serializer = AddDocumentToDocumentCollectionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = document_collection_document_service.add_document_collection_document(
            request.user,
            document_collection_id_int,
            document_id=serializer.validated_data["document_id"],
        )
        return Response(
            DocumentInDocumentCollectionResponse(link).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(
        self,
        request: Request,
        document_collection_pk: str | None = None,
        pk: str | None = None,
    ) -> Response:
        document_collection_document_service.remove_document_collection_document(
            request.user,
            int(document_collection_pk),
            int(pk),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
