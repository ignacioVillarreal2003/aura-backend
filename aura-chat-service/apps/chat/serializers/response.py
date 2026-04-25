from rest_framework import serializers
from apps.chat.models.chat import Chat


class ChatResponse(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = [
            "id",
            "name",
            "system_prompt",
            "response_style",
            "last_message_at",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]


class ChatListResponse(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Chat
        fields = [
            "id",
            "name",
            "last_message_at",
            "created_by",
            "created_at",
            "member_count",
        ]
