from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.serializers.webhook import WebhookCreateRequest, WebhookCreateResponse, WebhookResponse, WebhookUpdateRequest
from apps.chat.services.webhook_service import webhook_service
from core.openapi.common import standard_error_responses
from core.pagination.pagination import StandardPagination


class WebhookListView(APIView):
    @extend_schema(
        tags=["Webhooks"],
        summary="List webhooks for a chat",
        description="Paginated outgoing webhook subscriptions (URL, events, secret presence).",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={200: WebhookResponse(many=True), **standard_error_responses(401, 403, 404)},
    )
    def get(self, request: Request, chat_id: int) -> Response:
        hooks = webhook_service.list_webhooks(user=request.user, chat_id=chat_id)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(hooks, request)
        return paginator.get_paginated_response(WebhookResponse(page, many=True).data)

    @extend_schema(
        tags=["Webhooks"],
        summary="Create a webhook",
        description=(
            "Registers an HTTPS URL and a non-empty list of event names. "
            "The `secret` field is returned **only** in this response — store it to verify "
            "`X-Webhook-Signature` on incoming deliveries."
        ),
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request=WebhookCreateRequest,
        responses={201: WebhookCreateResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def post(self, request: Request, chat_id: int) -> Response:
        serializer = WebhookCreateRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        hook = webhook_service.create_webhook(
            user=request.user,
            chat_id=chat_id,
            url=serializer.validated_data["url"],
            events=serializer.validated_data["events"],
        )
        return Response(WebhookCreateResponse(hook).data, status=status.HTTP_201_CREATED)


class WebhookDetailView(APIView):
    @extend_schema(
        tags=["Webhooks"],
        summary="Update a webhook",
        description="Patch URL, events, or `is_active` without replacing unspecified fields (merge semantics in service).",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="webhook_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        request=WebhookUpdateRequest,
        responses={200: WebhookResponse, **standard_error_responses(400, 401, 403, 404)},
    )
    def patch(self, request: Request, chat_id: int, webhook_id: int) -> Response:
        serializer = WebhookUpdateRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        hook = webhook_service.update_webhook(
            user=request.user,
            chat_id=chat_id,
            webhook_id=webhook_id,
            **serializer.validated_data,
        )
        return Response(WebhookResponse(hook).data)

    @extend_schema(
        tags=["Webhooks"],
        summary="Delete a webhook",
        description="Removes the subscription permanently.",
        parameters=[
            OpenApiParameter(name="chat_id", type=int, location=OpenApiParameter.PATH, required=True),
            OpenApiParameter(name="webhook_id", type=int, location=OpenApiParameter.PATH, required=True),
        ],
        responses={204: OpenApiResponse(description="No content"), **standard_error_responses(401, 403, 404)},
    )
    def delete(self, request: Request, chat_id: int, webhook_id: int) -> Response:
        webhook_service.delete_webhook(
            user=request.user,
            chat_id=chat_id,
            webhook_id=webhook_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
