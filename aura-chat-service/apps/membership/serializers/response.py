from rest_framework import serializers

from apps.membership.dtos import ROLE_EDITOR, ROLE_OWNER, ROLE_READER
from apps.membership.models.chat_membership import ChatMembership


class ChatMembershipCheckResponse(serializers.Serializer):
    """Typed response for the internal chat-membership check.

    `role` is `null` exactly when `is_member` is `false`.
    """

    chat_id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    is_member = serializers.BooleanField()
    role = serializers.ChoiceField(choices=[ROLE_OWNER, ROLE_EDITOR, ROLE_READER], allow_null=True)


class MembershipResponse(serializers.ModelSerializer):
    chat_name = serializers.CharField(source='chat.name', read_only=True)

    class Meta:
        model = ChatMembership
        fields = [
            "id",
            "member_id",
            "chat_id",
            "chat_name",
            "status",
            "role",
            "joined_at",
            "left_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields
