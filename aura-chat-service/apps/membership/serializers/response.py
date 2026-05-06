from rest_framework import serializers

from apps.membership.models.chat_membership import ChatMembership


class MembershipResponse(serializers.ModelSerializer):
    class Meta:
        model = ChatMembership
        fields = [
            "id",
            "member_id",
            "chat_id",
            "status",
            "role",
            "joined_at",
            "left_at",
            "created_by",
            "created_at",
        ]
