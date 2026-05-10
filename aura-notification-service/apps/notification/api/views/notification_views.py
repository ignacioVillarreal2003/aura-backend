"""End-user notification inbox views."""

import logging

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notification.api.serializers import (
    BulkMarkReadResponseSerializer,
    ErrorResponseSerializer,
    MarkAllReadRequestSerializer,
    NotificationSerializer,
    NotificationStatusUpdateSerializer,
    UnreadCountSerializer,
)
from apps.notification.services import notification_service
from core.authorization import AccessControl
from core.authorization.permissions import (
    NOTIFICATION_DETAIL_GET,
    NOTIFICATION_HARD_DELETE,
    NOTIFICATION_INBOX_LIST,
    NOTIFICATION_MARK_ALL_READ_POST,
    NOTIFICATION_SOFT_DELETE,
    NOTIFICATION_STATUS_PATCH,
    NOTIFICATION_UNREAD_COUNT_GET,
)

logger = logging.getLogger(__name__)


class _NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


@extend_schema(tags=["Notifications"])
class NotificationListView(APIView):
    @extend_schema(
        summary="List notifications",
        description="Paginated list of notifications for the authenticated user. Soft-deleted records are excluded.",
        parameters=[
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by status (unread, read, archived). Repeatable."),
            OpenApiParameter("event_type", OpenApiTypes.STR, description="Filter by event_type."),
            OpenApiParameter("type", OpenApiTypes.STR, description="Filter by notification type."),
            OpenApiParameter("since", OpenApiTypes.DATETIME, description="Only return rows created at/after this timestamp."),
            OpenApiParameter("unread_only", OpenApiTypes.BOOL, description="Shortcut for status=unread."),
            OpenApiParameter("page", OpenApiTypes.INT),
            OpenApiParameter("page_size", OpenApiTypes.INT),
        ],
        responses={
            200: NotificationSerializer(many=True),
            401: ErrorResponseSerializer,
        },
    )
    def get(self, request):
        user = request.user
        AccessControl.require_permissions(user, frozenset({NOTIFICATION_INBOX_LIST}))

        status_filter = request.query_params.getlist("status") or None
        event_type = request.query_params.get("event_type")
        ntype = request.query_params.get("type")
        since = request.query_params.get("since")
        unread_only = request.query_params.get("unread_only", "").lower() in {"1", "true", "yes"}

        queryset = notification_service.list_for_user(
            user.id,
            status_in=status_filter,
            event_type=event_type,
            type=ntype,
            since=since,
            unread_only=unread_only,
        )

        paginator = _NotificationPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(tags=["Notifications"])
class NotificationUnreadCountView(APIView):
    @extend_schema(
        summary="Unread count",
        responses={200: UnreadCountSerializer, 401: ErrorResponseSerializer},
    )
    def get(self, request):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_UNREAD_COUNT_GET}))
        count = notification_service.unread_count(request.user.id)
        return Response({"count": count})


@extend_schema(tags=["Notifications"])
class NotificationDetailView(APIView):
    @extend_schema(
        summary="Notification detail",
        responses={
            200: NotificationSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def get(self, request, pk: int):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_DETAIL_GET}))
        notification = notification_service.get_for_user(request.user.id, pk)
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        summary="Update notification status",
        request=NotificationStatusUpdateSerializer,
        responses={
            200: NotificationSerializer,
            400: ErrorResponseSerializer,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def patch(self, request, pk: int):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_STATUS_PATCH}))
        serializer = NotificationStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification = notification_service.update_status(
            request.user.id, pk, serializer.validated_data["status"]
        )
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        summary="Soft-delete a notification",
        responses={
            204: None,
            401: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def delete(self, request, pk: int):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_SOFT_DELETE}))
        notification_service.soft_delete(request.user.id, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Notifications"])
class MarkAllReadView(APIView):
    @extend_schema(
        summary="Mark all notifications as read",
        request=MarkAllReadRequestSerializer,
        responses={200: BulkMarkReadResponseSerializer, 401: ErrorResponseSerializer},
    )
    def post(self, request):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_MARK_ALL_READ_POST}))
        serializer = MarkAllReadRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        updated = notification_service.mark_all_read(
            request.user.id,
            until_id=serializer.validated_data.get("until_id"),
        )
        return Response({"updated": updated})


@extend_schema(tags=["Notifications"])
class NotificationHardDeleteView(APIView):
    @extend_schema(
        summary="Hard delete (`NOTIFICATION_HARD_DELETE`)",
        responses={
            204: None,
            401: ErrorResponseSerializer,
            403: ErrorResponseSerializer,
            404: ErrorResponseSerializer,
        },
    )
    def delete(self, request, pk: int):
        AccessControl.require_permissions(request.user, frozenset({NOTIFICATION_HARD_DELETE}))
        notification_service.hard_delete(pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
