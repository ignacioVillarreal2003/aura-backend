"""Notification API views."""

from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from notifications.models import Notification, NotificationStatus
from notifications.api.serializers import (
    NotificationSerializer,
    NotificationCreateSerializer,
    NotificationStatusUpdateSerializer,
    ErrorResponseSerializer,
    BulkCreateResponseSerializer,
)
from notifications.services.auth_client import get_user_from_request


def _is_internal_request(request) -> bool:
    token = request.headers.get('X-Internal-Token', '')
    return bool(token) and token == settings.NOTIFICATION_INTERNAL_API_TOKEN


class NotificationListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary='List notifications',
        description=(
            'Returns paginated notifications for the authenticated user. '
            'Excludes soft-deleted records. Filterable by status.'
        ),
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description='Filter by status: unread, read, archived'),
        ],
        responses={200: NotificationSerializer(many=True), 401: ErrorResponseSerializer},
        tags=['Notifications'],
    )
    def get(self, request):
        user = get_user_from_request(request)
        if not user:
            return Response({'detail': 'Invalid or missing token.'}, status=status.HTTP_401_UNAUTHORIZED)

        queryset = Notification.objects.filter(
            receiver_id=user['user_id'],
            deleted_at__isnull=True,
        )

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(queryset, request)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary='Create notification(s)',
        description=(
            'Create one or many in-app notifications. '
            'Accepts a list of receiver_ids to enable bulk targeting (e.g. all users with a role).'
        ),
        request=NotificationCreateSerializer,
        responses={201: BulkCreateResponseSerializer, 400: ErrorResponseSerializer, 401: ErrorResponseSerializer},
        tags=['Notifications'],
    )
    def post(self, request):
        user = get_user_from_request(request)
        if not user:
            return Response({'detail': 'Invalid or missing token.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = NotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        receiver_ids = serializer.validated_data['receiver_ids']
        message = serializer.validated_data['message']
        notification_type = serializer.validated_data['type']
        sender_name = serializer.validated_data.get('sender_name')
        target_scope = serializer.validated_data.get('target_scope', 'individual')
        target_label = serializer.validated_data.get('target_label')

        to_create = []

        for receiver_id in receiver_ids:
            to_create.append(
                Notification(
                    receiver_id=receiver_id,
                    message=message,
                    type=notification_type,
                    sender_name=sender_name,
                    target_scope=target_scope,
                    target_label=target_label,
                    status=NotificationStatus.UNREAD,
                    created_by=user['user_id'],
                    updated_by=user['user_id'],
                )
            )

        created_objects = Notification.objects.bulk_create(to_create)

        return Response(
            {
                'created': len(created_objects),
                'notifications': NotificationSerializer(created_objects, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


class NotificationStatusView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary='Update notification status',
        description='Transition a notification to "read" or "archived". Only the notification owner can do this.',
        request=NotificationStatusUpdateSerializer,
        responses={200: NotificationSerializer, 400: ErrorResponseSerializer, 401: ErrorResponseSerializer, 404: ErrorResponseSerializer},
        tags=['Notifications'],
    )
    def patch(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({'detail': 'Invalid or missing token.'}, status=status.HTTP_401_UNAUTHORIZED)

        notification = Notification.objects.filter(
            pk=pk,
            receiver_id=user['user_id'],
            deleted_at__isnull=True,
        ).first()
        if not notification:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = NotificationStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        if new_status == NotificationStatus.READ:
            notification.mark_read(updated_by=user['user_id'])
        else:
            notification.archive(updated_by=user['user_id'])

        return Response(NotificationSerializer(notification).data)


class NotificationDeleteView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary='Soft delete notification',
        description='Soft-deletes a notification. The record remains in the database for audit purposes.',
        responses={204: None, 401: ErrorResponseSerializer, 404: ErrorResponseSerializer},
        tags=['Notifications'],
    )
    def delete(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({'detail': 'Invalid or missing token.'}, status=status.HTTP_401_UNAUTHORIZED)

        notification = Notification.objects.filter(
            pk=pk,
            receiver_id=user['user_id'],
            deleted_at__isnull=True,
        ).first()
        if not notification:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        notification.soft_delete(deleted_by=user['user_id'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationHardDeleteView(APIView):
    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary='Hard delete notification (superadmin)',
        description='Permanently removes a notification from the database. Requires is_super_admin.',
        responses={204: None, 401: ErrorResponseSerializer, 403: ErrorResponseSerializer, 404: ErrorResponseSerializer},
        tags=['Notifications'],
    )
    def delete(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({'detail': 'Invalid or missing token.'}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.get('is_super_admin'):
            return Response({'detail': 'Superadmin required.'}, status=status.HTTP_403_FORBIDDEN)

        notification = Notification.objects.filter(pk=pk).first()
        if not notification:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InternalAdminNotificationCreateView(APIView):
    """
    Trusted internal endpoint for admin-triggered creation from aura-auth-service.
    Auth: X-Internal-Token header.
    """

    authentication_classes = []
    permission_classes = []

    @extend_schema(
        summary='Internal admin create notifications',
        description='Internal endpoint for trusted backend-to-backend notification creation.',
        request=NotificationCreateSerializer,
        responses={201: BulkCreateResponseSerializer, 401: ErrorResponseSerializer},
        tags=['Internal'],
    )
    def post(self, request):
        if not _is_internal_request(request):
            return Response({'detail': 'Unauthorized internal call.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = NotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        receiver_ids = serializer.validated_data['receiver_ids']
        message = serializer.validated_data['message']
        notification_type = serializer.validated_data['type']
        sender_name = serializer.validated_data.get('sender_name')
        target_scope = serializer.validated_data.get('target_scope', 'individual')
        target_label = serializer.validated_data.get('target_label')
        actor_user_id = serializer.validated_data.get('actor_user_id')

        to_create = [
            Notification(
                receiver_id=receiver_id,
                message=message,
                type=notification_type,
                sender_name=sender_name,
                target_scope=target_scope,
                target_label=target_label,
                status=NotificationStatus.UNREAD,
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
            for receiver_id in receiver_ids
        ]

        created_objects = Notification.objects.bulk_create(to_create)

        return Response(
            {
                'created': len(created_objects),
                'notifications': NotificationSerializer(created_objects, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )
