from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
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


@extend_schema(
    auth=[
        {"bearerAuth": []},
        {
            "serviceApiKey": [],
            "serviceUserId": [],
            "serviceUserEmail": [],
        },
    ],
)
@extend_schema_view(
    list=extend_schema(
        tags=["DocumentCollections"],
        summary="List document collections",
        responses={
            200: DocumentCollectionResponse(many=True),
            **_ERR_LIST,
        },
    ),
    create=extend_schema(
        tags=["DocumentCollections"],
        summary="Create document collection",
        request=CreateDocumentCollectionRequest,
        responses={
            201: DocumentCollectionResponse,
            **_ERR_WRITE,
        },
    ),
    retrieve=extend_schema(
        tags=["DocumentCollections"],
        summary="Get document collection",
        responses={
            200: DocumentCollectionResponse,
            **_ERR_RETRIEVE,
        },
    ),
    partial_update=extend_schema(
        tags=["DocumentCollections"],
        summary="Update document collection",
        request=PatchDocumentCollectionRequest,
        responses={
            200: DocumentCollectionResponse,
            **_ERR_WRITE,
        },
    ),
    destroy=extend_schema(
        tags=["DocumentCollections"],
        summary="Delete document collection",
        responses={
            204: OpenApiResponse(description="No content"),
            **_ERR_DESTROY,
        },
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
        qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(DocumentCollectionResponse(page, many=True).data)

    def create(self, request: Request) -> Response:
        serializer = CreateDocumentCollectionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_collection = document_collection_service.create_document_collection(
            request.user,
            serializer.validated_data["name"],
        )
        return Response(
            DocumentCollectionResponse(document_collection).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        document_collection = document_collection_service.get_document_collection(
            request.user,
            int(pk),
        )
        return Response(DocumentCollectionResponse(document_collection).data)

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        serializer = PatchDocumentCollectionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_collection = document_collection_service.update_document_collection(
            request.user,
            int(pk),
            name=serializer.validated_data["name"],
        )
        return Response(DocumentCollectionResponse(document_collection).data)

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        document_collection_service.delete_document_collection(request.user, int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
