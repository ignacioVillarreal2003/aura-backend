from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.document_collections.serializers.request import (
    CreateDocumentCollectionRequest,
    PatchDocumentCollectionRequest,
)
from apps.document_collections.serializers.response import DocumentCollectionResponse
from apps.document_collections.services.document_collection_service import (
    document_collection_service,
)
from core.pagination.pagination import StandardPagination


@extend_schema_view(
    list=extend_schema(
        tags=["DocumentCollections"],
        summary="List document collections",
        responses={200: DocumentCollectionResponse(many=True)},
    ),
    create=extend_schema(
        tags=["DocumentCollections"],
        summary="Create document collection",
        request=CreateDocumentCollectionRequest,
        responses={201: DocumentCollectionResponse},
    ),
    retrieve=extend_schema(
        tags=["DocumentCollections"],
        summary="Get document collection",
        responses={200: DocumentCollectionResponse},
    ),
    partial_update=extend_schema(
        tags=["DocumentCollections"],
        summary="Update document collection",
        request=PatchDocumentCollectionRequest,
        responses={200: DocumentCollectionResponse},
    ),
    destroy=extend_schema(
        tags=["DocumentCollections"],
        summary="Delete document collection",
        responses={204: OpenApiResponse(description="No content")},
    ),
)
class DocumentCollectionViewSet(ViewSet):
    def list(self, request: Request) -> Response:
        qs = document_collection_service.list_document_collections(request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            DocumentCollectionResponse(page, many=True).data
        )

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

    def retrieve(self, request: Request, document_collection_id: str | None = None) -> Response:
        document_collection = document_collection_service.get_document_collection(
            request.user,
            int(document_collection_id),
        )
        return Response(DocumentCollectionResponse(document_collection).data)

    def partial_update(self, request: Request, document_collection_id: str | None = None) -> Response:
        serializer = PatchDocumentCollectionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_collection = document_collection_service.update_document_collection(
            request.user,
            int(document_collection_id),
            name=serializer.validated_data["name"],
        )
        return Response(DocumentCollectionResponse(document_collection).data)

    def destroy(self, request: Request, document_collection_id: str | None = None) -> Response:
        document_collection_service.delete_document_collection(request.user, int(document_collection_id))
        return Response(status=status.HTTP_204_NO_CONTENT)
