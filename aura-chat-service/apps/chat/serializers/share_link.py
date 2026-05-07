from django.utils import timezone
from rest_framework import serializers

from apps.chat.models.chat_share_link import ChatShareLink


class ShareLinkCreateRequest(serializers.Serializer):
    expires_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text="Optional UTC expiry; links stay valid until this time. Must be in the future if set.",
    )

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("expires_at must be in the future.")
        return value


class ShareLinkResponse(serializers.ModelSerializer):
    class Meta:
        model = ChatShareLink
        fields = ["id", "chat_id", "token", "created_by", "created_at", "expires_at", "is_active"]
