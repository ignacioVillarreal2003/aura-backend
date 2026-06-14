from datetime import datetime
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.chat.models.chat import Chat


class ChatResponse(serializers.ModelSerializer):
    is_pinned = serializers.SerializerMethodField()
    archived_at = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = [
            "id",
            "name",
            "system_prompt",
            "response_style",
            "tags",
            "is_locked",
            "is_pinned",
            "archived_at",
            "last_message_at",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_is_pinned(self, obj) -> bool:
        return getattr(obj, "pinned_at", None) is not None

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_archived_at(self, obj) -> datetime | None:
        return getattr(obj, "archived_at", None)


class ChatListResponse(serializers.ModelSerializer):
    member_count = serializers.IntegerField(
        read_only=True,
        help_text="Number of members in the chat (annotated for list endpoints).",
    )
    unread_count = serializers.IntegerField(
        read_only=True,
        help_text="Unread message count for the current user (annotated).",
    )
    is_pinned = serializers.SerializerMethodField()
    archived_at = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = [
            "id",
            "name",
            "tags",
            "is_locked",
            "last_message_at",
            "created_by",
            "created_at",
            "member_count",
            "unread_count",
            "is_pinned",
            "archived_at",
        ]

    @extend_schema_field(serializers.BooleanField(help_text="True if this chat is pinned for the current user."))
    def get_is_pinned(self, obj) -> bool:
        return getattr(obj, "pinned_at", None) is not None

    @extend_schema_field(
        serializers.DateTimeField(
            allow_null=True,
            help_text="When the user archived this chat, if archived.",
        )
    )
    def get_archived_at(self, obj) -> datetime | None:
        return getattr(obj, "archived_at", None)


class ChatManageListResponse(serializers.ModelSerializer):
    member_count = serializers.IntegerField(
        read_only=True,
        help_text="Number of active members in the chat (annotated).",
    )

    class Meta:
        model = Chat
        fields = [
            "id",
            "name",
            "tags",
            "is_locked",
            "last_message_at",
            "created_by",
            "created_at",
            "member_count",
        ]
        read_only_fields = fields
