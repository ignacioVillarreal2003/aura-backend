from django.utils import timezone
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
            "tags",
            "is_ephemeral",
            "is_locked",
            "last_message_at",
            "is_archived",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]


class ChatListResponse(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    unread_count = serializers.IntegerField(read_only=True)
    is_pinned = serializers.SerializerMethodField()
    archived_at = serializers.SerializerMethodField()
    is_muted = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = [
            "id",
            "name",
            "tags",
            "is_ephemeral",
            "is_locked",
            "last_message_at",
            "is_archived",
            "created_by",
            "created_at",
            "member_count",
            "unread_count",
            "is_pinned",
            "archived_at",
            "is_muted",
        ]

    def get_is_pinned(self, obj) -> bool:
        return getattr(obj, "pinned_at", None) is not None

    def get_archived_at(self, obj):
        return getattr(obj, "archived_at", None)

    def get_is_muted(self, obj) -> bool:
        muted_until = getattr(obj, "muted_until", None)
        if muted_until is None:
            return False
        return muted_until > timezone.now()
