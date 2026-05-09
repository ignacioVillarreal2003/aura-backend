from rest_framework import serializers

from apps.notification.models import Notification, NotificationStatus


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "receiver_id",
            "message",
            "type",
            "event_type",
            "event_key",
            "data",
            "severity",
            "link_url",
            "sender_name",
            "target_scope",
            "target_label",
            "status",
            "read_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class NotificationStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=NotificationStatus.choices)


class MarkAllReadRequestSerializer(serializers.Serializer):
    until_id = serializers.IntegerField(min_value=1, required=False)


class BulkMarkReadResponseSerializer(serializers.Serializer):
    updated = serializers.IntegerField()


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()
    detail = serializers.CharField()
    status_code = serializers.IntegerField()
