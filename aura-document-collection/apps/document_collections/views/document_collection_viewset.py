from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.document_collections.serializers.document_collection_serializers import (
    DocumentCollectionSerializer,
    DocumentInCollectionSerializer,
    UserInCollectionSerializer,
    collection_to_dict,
    document_link_to_dict,
    user_membership_to_dict,
)
from apps.document_collections.serializers.request_serializers import (
    AddDocumentToCollectionSerializer,
    AddUserToCollectionSerializer,
    CreateDocumentCollectionSerializer,
    PatchDocumentCollectionSerializer,
)
from apps.document_collections.services.document_collection_service import (
    document_collection_service,
)
from core.pagination.pagination import StandardPagination


@extend_schema_view(
    list=extend_schema(
        tags=["DocumentCollections"],
        summary="List document collections",
        responses={200: DocumentCollectionSerializer(many=True)},
    ),
    create=extend_schema(
        tags=["DocumentCollections"],
        summary="Create document collection",
        request=CreateDocumentCollectionSerializer,
        responses={201: DocumentCollectionSerializer},
    ),
    retrieve=extend_schema(
        tags=["DocumentCollections"],
        summary="Get document collection",
        responses={200: DocumentCollectionSerializer},
    ),
    partial_update=extend_schema(
        tags=["DocumentCollections"],
        summary="Update document collection",
        request=PatchDocumentCollectionSerializer,
        responses={200: DocumentCollectionSerializer},
    ),
    destroy=extend_schema(
        tags=["DocumentCollections"],
        summary="Delete document collection",
        responses={204: OpenApiResponse(description="No content")},
    ),
)
class DocumentCollectionViewSet(ViewSet):
    lookup_value_regex = r"[0-9]+"

    def list(self, request: Request) -> Response:
        qs = document_collection_service.list_collections(request.user)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        data = [collection_to_dict(c) for c in page]
        return paginator.get_paginated_response(data)

    def create(self, request: Request) -> Response:
        serializer = CreateDocumentCollectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        collection = document_collection_service.create_collection(
            request.user,
            serializer.validated_data["name"],
        )
        return Response(collection_to_dict(collection), status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        collection = document_collection_service.get_collection(request.user, int(pk))
        return Response(collection_to_dict(collection))

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        serializer = PatchDocumentCollectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        collection = document_collection_service.update_collection(
            request.user,
            int(pk),
            name=serializer.validated_data["name"],
        )
        return Response(collection_to_dict(collection))

    def destroy(self, request: Request, pk: str | None = None) -> Response:
        document_collection_service.delete_collection(request.user, int(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        methods=["GET"],
        tags=["CollectionUsers"],
        summary="List users in collection",
        responses={200: UserInCollectionSerializer(many=True)},
    )
    @extend_schema(
        methods=["POST"],
        tags=["CollectionUsers"],
        summary="Add user to collection",
        request=AddUserToCollectionSerializer,
        responses={201: UserInCollectionSerializer},
    )
    @action(detail=True, methods=["get", "post"], url_path="users")
    def collection_users(self, request: Request, pk: str | None = None) -> Response:
        collection_id = int(pk)
        if request.method == "GET":
            qs = document_collection_service.list_users(request.user, collection_id)
            paginator = StandardPagination()
            page = paginator.paginate_queryset(qs, request)
            data = [user_membership_to_dict(row) for row in page]
            return paginator.get_paginated_response(data)

        serializer = AddUserToCollectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = document_collection_service.add_user(
            request.user,
            collection_id,
            user_id_to_add=serializer.validated_data["user_id"],
        )
        return Response(
            user_membership_to_dict(membership),
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["CollectionUsers"],
        summary="Remove user from collection (or leave)",
        responses={204: OpenApiResponse(description="No content")},
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"users/(?P<link_id>[0-9]+)",
    )
    def collection_users_destroy(
        self,
        request: Request,
        pk: str | None = None,
        link_id: str | None = None,
    ) -> Response:
        document_collection_service.remove_user_membership(
            request.user,
            int(pk),
            int(link_id),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        methods=["GET"],
        tags=["CollectionDocuments"],
        summary="List documents in collection",
        responses={200: DocumentInCollectionSerializer(many=True)},
    )
    @extend_schema(
        methods=["POST"],
        tags=["CollectionDocuments"],
        summary="Link document to collection",
        request=AddDocumentToCollectionSerializer,
        responses={201: DocumentInCollectionSerializer},
    )
    @action(detail=True, methods=["get", "post"], url_path="documents")
    def collection_documents(self, request: Request, pk: str | None = None) -> Response:
        collection_id = int(pk)
        if request.method == "GET":
            qs = document_collection_service.list_documents(request.user, collection_id)
            paginator = StandardPagination()
            page = paginator.paginate_queryset(qs, request)
            data = [document_link_to_dict(row) for row in page]
            return paginator.get_paginated_response(data)

        serializer = AddDocumentToCollectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = document_collection_service.add_document(
            request.user,
            collection_id,
            document_id=serializer.validated_data["document_id"],
        )
        return Response(document_link_to_dict(link), status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["CollectionDocuments"],
        summary="Unlink document from collection",
        responses={204: OpenApiResponse(description="No content")},
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"documents/(?P<link_id>[0-9]+)",
    )
    def collection_documents_destroy(
        self,
        request: Request,
        pk: str | None = None,
        link_id: str | None = None,
    ) -> Response:
        document_collection_service.remove_document_link(
            request.user,
            int(pk),
            int(link_id),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
