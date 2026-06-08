from rest_framework import serializers

from apps.membership.models.chat_membership import ChatMembership


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
