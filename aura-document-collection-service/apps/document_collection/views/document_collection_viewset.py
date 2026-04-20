from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.document_collection.serializers.document_collection_serializers import (
    DocumentCollectionSerializer,
    document_collection_to_dict,
)
from apps.document_collection.serializers.request_serializers import (
    CreateDocumentCollectionSerializer,
    PatchDocumentCollectionSerializer,
)
from apps.document_collection.services.document_collection_service import (
    document_collection_service,
)
from core.pagination.pagination import StandardPagination


class DocumentCollectionViewSet(ViewSet):
    @extend_schema(
        tags=["DocumentCollections"],
        summary="List document collections",
        responses={200: DocumentCollectionSerializer(many=True)},
    )
    def list(self, request: Request) -> Response:
        qs = document_collection_service.list_document_collections(request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        data = [document_collection_to_dict(dc) for dc in page]
        return paginator.get_paginated_response(data)

    @extend_schema(
        tags=["DocumentCollections"],
        summary="Create document collection",
        request=CreateDocumentCollectionSerializer,
        responses={201: DocumentCollectionSerializer},
    )
    def create(self, request: Request) -> Response:
        serializer = CreateDocumentCollectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_collection = document_collection_service.create_document_collection(
            request.user,
            serializer.validated_data["name"],
        )
        return Response(
            document_collection_to_dict(document_collection),
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["DocumentCollections"],
        summary="Get document collection",
        responses={200: DocumentCollectionSerializer},
    )
    def retrieve(self, request: Request, document_collection_id: str | None = None) -> Response:
        document_collection = document_collection_service.get_document_collection(
            request.user,
            int(document_collection_id),
        )
        return Response(document_collection_to_dict(document_collection))

    @extend_schema(
        tags=["DocumentCollections"],
        summary="Update document collection",
        request=PatchDocumentCollectionSerializer,
        responses={200: DocumentCollectionSerializer},
    )
    def partial_update(self, request: Request, document_collection_id: str | None = None) -> Response:
        serializer = PatchDocumentCollectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_collection = document_collection_service.update_document_collection(
            request.user,
            int(document_collection_id),
            name=serializer.validated_data["name"],
        )
        return Response(document_collection_to_dict(document_collection))

    @extend_schema(
        tags=["DocumentCollections"],
        summary="Delete document collection",
        responses={204: OpenApiResponse(description="No content")},
    )
    def destroy(self, request: Request, document_collection_id: str | None = None) -> Response:
        document_collection_service.delete_document_collection(request.user, int(document_collection_id))
        return Response(status=status.HTTP_204_NO_CONTENT)
