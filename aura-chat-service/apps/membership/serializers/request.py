from rest_framework import serializers

from apps.membership.models.chat_membership import ChatMembership


class AddMemberRequest(serializers.Serializer):
    member_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=50,
    )


class UpdateMemberRequest(serializers.Serializer):
    status = serializers.ChoiceField(choices=ChatMembership.Status.choices)


class UpdateRoleRequest(serializers.Serializer):
    role = serializers.ChoiceField(choices=ChatMembership.Role.choices)
