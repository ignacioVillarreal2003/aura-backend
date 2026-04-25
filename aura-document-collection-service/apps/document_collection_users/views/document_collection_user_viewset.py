from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.document_collection_users.filters import UserInDocumentCollectionFilter
from apps.document_collection_users.models import UserInDocumentCollection
from apps.document_collection_users.serializers.request import AddUserToDocumentCollectionRequest
from apps.document_collection_users.serializers.response import UserInDocumentCollectionResponse
from apps.document_collection_users.services.document_collection_user_service import (
    document_collection_user_service,
)
from core.authentication.authenticated_user import AuthenticatedUser
from core.integrations.user_profile_client import UserProfile, user_profile_client
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination

_ERR_LIST = standard_error_responses(401, 403, 404, 503)
_ERR_CREATE = standard_error_responses(400, 401, 403, 404, 409, 503)
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
        tags=["DocumentCollectionUsers"],
        summary="List users in document collection",
        description=(
            "Paginated membership rows. Responses include `profiles_enrichment`: "
            "`complete`, `degraded`, or `failed` depending on the user profile service."
        ),
        responses={
            200: UserInDocumentCollectionResponse(many=True),
            **_ERR_LIST,
        },
    ),
    create=extend_schema(
        tags=["DocumentCollectionUsers"],
        summary="Add user to document collection",
        request=AddUserToDocumentCollectionRequest,
        description="Response body includes `profiles_enrichment` alongside the membership payload.",
        responses={
            201: UserInDocumentCollectionResponse,
            **_ERR_CREATE,
        },
    ),
    destroy=extend_schema(
        tags=["DocumentCollectionUsers"],
        summary="Remove user from document collection",
        responses={
            204: OpenApiResponse(description="No content"),
            **_ERR_DESTROY,
        },
    ),
)
class DocumentCollectionUserViewSet(GenericViewSet):
    queryset = UserInDocumentCollection.objects.none()
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = UserInDocumentCollectionFilter
    ordering_fields = ["id", "created_at", "user_id"]
    ordering = ["id"]
    lookup_value_regex = r"[1-9][0-9]*"

    def list(self, request: Request, document_collection_pk: str | None = None) -> Response:
        document_collection_id_int = int(document_collection_pk)
        qs = document_collection_user_service.list_document_collection_users(
            request.user,
            document_collection_id_int,
        )
        qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        user_ids = [row.user_id for row in page]
        actor: AuthenticatedUser = request.user
        profiles_result = user_profile_client.fetch_by_ids(user_ids, authenticated_user=actor)
        response = self.get_paginated_response(
            UserInDocumentCollectionResponse(
                page,
                many=True,
                context={"profiles": profiles_result.profiles},
            ).data
        )
        if isinstance(response.data, dict):
            response.data["profiles_enrichment"] = profiles_result.enrichment
        return response

    def create(self, request: Request, document_collection_pk: str | None = None) -> Response:
        document_collection_id_int = int(document_collection_pk)
        serializer = AddUserToDocumentCollectionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = document_collection_user_service.add_document_collection_user(
            request.user,
            document_collection_id_int,
            user_id=serializer.validated_data["user_id"],
        )
        actor: AuthenticatedUser = request.user
        profiles_result = user_profile_client.fetch_by_ids(
            [membership.user_id],
            authenticated_user=actor,
        )
        profile = profiles_result.profiles.get(membership.user_id) or UserProfile(
            id=membership.user_id,
            email="",
            username="",
        )
        body = UserInDocumentCollectionResponse(
            membership,
            context={"profiles": {membership.user_id: profile}},
        ).data
        if isinstance(body, dict):
            body = {**body, "profiles_enrichment": profiles_result.enrichment}
        return Response(body, status=status.HTTP_201_CREATED)

    def destroy(
        self,
        request: Request,
        document_collection_pk: str | None = None,
        pk: str | None = None,
    ) -> Response:
        document_collection_user_service.remove_document_collection_user(
            request.user,
            int(document_collection_pk),
            int(pk),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
