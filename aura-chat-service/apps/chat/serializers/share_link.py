from rest_framework import serializers

from apps.chat.models.chat_share_link import ChatShareLink


class ShareLinkCreateRequest(serializers.Serializer):
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class ShareLinkResponse(serializers.ModelSerializer):
    class Meta:
        model = ChatShareLink
        fields = ["id", "chat_id", "token", "created_by", "created_at", "expires_at", "is_active"]
