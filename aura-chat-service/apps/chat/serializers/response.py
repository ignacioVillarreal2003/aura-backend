from datetime import datetime
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
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
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]


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
            "created_by",
            "created_at",
            "member_count",
            "unread_count",
            "is_pinned",
            "archived_at",
            "is_muted",
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

    @extend_schema_field(
        serializers.BooleanField(
            help_text="True if `muted_until` is set and still in the future for this user.",
        )
    )
    def get_is_muted(self, obj) -> bool:
        muted_until = getattr(obj, "muted_until", None)
        if muted_until is None:
            return False
        return muted_until > timezone.now()


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
            "is_ephemeral",
            "is_locked",
            "last_message_at",
            "created_by",
            "created_at",
            "member_count",
        ]
        read_only_fields = fields
