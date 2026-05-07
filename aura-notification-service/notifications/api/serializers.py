"""Serializers for notification API endpoints."""

from rest_framework import serializers
from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id',
            'receiver_id',
            'message',
            'type',
            'sender_name',
            'target_scope',
            'target_label',
            'status',
            'read_at',
            'created_by',
            'created_at',
        ]
        read_only_fields = ['id', 'read_at', 'created_at']


class NotificationCreateSerializer(serializers.Serializer):
    """Used for creating one or many notifications in a single request."""

    receiver_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        help_text='List of auth_user.id values to notify. Use a single-element list for one user.',
    )
    message = serializers.CharField(max_length=500)
    type = serializers.CharField(max_length=64)
    target_scope = serializers.CharField(
        max_length=64,
        required=False,
        default='individual',
    )
    target_label = serializers.CharField(max_length=255, required=False, allow_blank=True)
    actor_user_id = serializers.IntegerField(min_value=1, required=False)


class NotificationStatusUpdateSerializer(serializers.Serializer):
    status = serializers.CharField(
        max_length=64,
        help_text='Target status string (domain-defined; e.g. read, archived).',
    )


# Response serializers for drf-spectacular schema
class ErrorResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class BulkCreateResponseSerializer(serializers.Serializer):
    created = serializers.IntegerField(help_text='Number of notifications created')
    notifications = NotificationSerializer(many=True)
