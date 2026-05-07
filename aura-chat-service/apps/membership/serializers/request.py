from rest_framework import serializers

from apps.membership.models.chat_membership import ChatMembership


class AddMemberRequest(serializers.Serializer):
    member_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=50,
        help_text="User ids to invite (deduplicated, max 50).",
    )

    def validate_member_ids(self, value):
        return list(dict.fromkeys(value))


class UpdateMemberRequest(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=ChatMembership.Status.choices,
        help_text="Target membership state (transitions validated server-side).",
    )


class UpdateRoleRequest(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=ChatMembership.Role.choices,
        help_text="New role: owner, editor, or reader.",
    )
