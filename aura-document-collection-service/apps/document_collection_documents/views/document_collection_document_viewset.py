from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
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
        tags=["DocumentCollectionDocuments"],
        summary="List documents in document collection",
        responses={
            200: DocumentInDocumentCollectionResponse(many=True),
            **_ERR_LIST,
        },
    ),
    create=extend_schema(
        tags=["DocumentCollectionDocuments"],
        summary="Link document to document collection",
        request=AddDocumentToDocumentCollectionRequest,
        responses={
            201: DocumentInDocumentCollectionResponse,
            **_ERR_CREATE,
        },
    ),
    destroy=extend_schema(
        tags=["DocumentCollectionDocuments"],
        summary="Unlink document from document collection",
        responses={
            204: OpenApiResponse(description="No content"),
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
