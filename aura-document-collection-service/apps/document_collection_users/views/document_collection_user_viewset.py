from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.document_collection_users.serializers.request import AddUserToDocumentCollectionRequest
from apps.document_collection_users.serializers.response import UserInDocumentCollectionResponse
from apps.document_collection_users.services.document_collection_user_service import (
    document_collection_user_service,
)
from core.authentication.authenticated_user import AuthenticatedUser
from core.integrations.user_profile_client import UserProfile, user_profile_client
from core.pagination.pagination import StandardPagination


@extend_schema_view(
    list=extend_schema(
        tags=["DocumentCollectionUsers"],
        summary="List users in document collection",
        responses={200: UserInDocumentCollectionResponse(many=True)},
    ),
    create=extend_schema(
        tags=["DocumentCollectionUsers"],
        summary="Add user to document collection",
        request=AddUserToDocumentCollectionRequest,
        responses={201: UserInDocumentCollectionResponse},
    ),
    destroy=extend_schema(
        tags=["DocumentCollectionUsers"],
        summary="Remove user from document collection",
        responses={204: OpenApiResponse(description="No content")},
    ),
)
class DocumentCollectionUserViewSet(ViewSet):
    def list(self, request: Request, document_collection_id: str | None = None) -> Response:
        document_collection_id_int = int(document_collection_id)
        qs = document_collection_user_service.list_document_collection_users(
            request.user,
            document_collection_id_int,
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        user_ids = [row.user_id for row in page]
        actor: AuthenticatedUser = request.user
        profiles = user_profile_client.fetch_by_ids(user_ids, authenticated_user=actor)
        return paginator.get_paginated_response(
            UserInDocumentCollectionResponse(page, many=True, context={"profiles": profiles}).data
        )

    def create(self, request: Request, document_collection_id: str | None = None) -> Response:
        document_collection_id_int = int(document_collection_id)
        serializer = AddUserToDocumentCollectionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = document_collection_user_service.add_document_collection_user(
            request.user,
            document_collection_id_int,
            user_id=serializer.validated_data["user_id"],
        )
        actor: AuthenticatedUser = request.user
        profiles = user_profile_client.fetch_by_ids(
            [membership.user_id],
            authenticated_user=actor,
        )
        profile = profiles.get(membership.user_id) or UserProfile(
            id=membership.user_id,
            email="",
            username="",
        )
        return Response(
            UserInDocumentCollectionResponse(
                membership,
                context={"profiles": {membership.user_id: profile}},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(
        self,
        request: Request,
        document_collection_id: str | None = None,
        user_id: str | None = None,
    ) -> Response:
        document_collection_user_service.remove_document_collection_user(
            request.user,
            int(document_collection_id),
            int(user_id),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
