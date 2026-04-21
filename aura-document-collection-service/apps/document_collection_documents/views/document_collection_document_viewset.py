from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.document_collection_documents.serializers.request import AddDocumentToDocumentCollectionRequest
from apps.document_collection_documents.serializers.response import DocumentInDocumentCollectionResponse
from apps.document_collection_documents.services.document_collection_document_service import (
    document_collection_document_service,
)
from core.pagination.pagination import StandardPagination


@extend_schema_view(
    list=extend_schema(
        tags=["DocumentCollectionDocuments"],
        summary="List documents in document collection",
        responses={200: DocumentInDocumentCollectionResponse(many=True)},
    ),
    create=extend_schema(
        tags=["DocumentCollectionDocuments"],
        summary="Link document to document collection",
        request=AddDocumentToDocumentCollectionRequest,
        responses={201: DocumentInDocumentCollectionResponse},
    ),
    destroy=extend_schema(
        tags=["DocumentCollectionDocuments"],
        summary="Unlink document from document collection",
        responses={204: OpenApiResponse(description="No content")},
    ),
)
class DocumentCollectionDocumentViewSet(ViewSet):
    def list(self, request: Request, document_collection_id: str | None = None) -> Response:
        document_collection_id_int = int(document_collection_id)
        qs = document_collection_document_service.list_document_collection_documents(
            request.user,
            document_collection_id_int,
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            DocumentInDocumentCollectionResponse(page, many=True).data
        )

    def create(self, request: Request, document_collection_id: str | None = None) -> Response:
        document_collection_id_int = int(document_collection_id)
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
        document_collection_id: str | None = None,
        document_id: str | None = None,
    ) -> Response:
        document_collection_document_service.remove_document_collection_document(
            request.user,
            int(document_collection_id),
            int(document_id),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
