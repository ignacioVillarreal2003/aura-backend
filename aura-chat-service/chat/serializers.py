from rest_framework import serializers
from .models import Chat, ChatMembership, ChatMessage


class ChatMembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMembership
        fields = ['id', 'member_id', 'status', 'joined_at']


class ChatSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    chat_type = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = [
            'id', 'name', 'system_prompt', 'response_style',
            'chat_type', 'last_message_at', 'members',
            'created_by', 'created_at', 'updated_at',
        ]

    def get_members(self, obj):
        active = obj.memberships.filter(deleted_at__isnull=True)
        return ChatMembershipSerializer(active, many=True).data

    def get_chat_type(self, obj):
        count = obj.memberships.filter(deleted_at__isnull=True).count()
        return 'group' if count > 1 else 'individual'


class ChatSummarySerializer(serializers.ModelSerializer):
    chat_type = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = ['id', 'name', 'chat_type', 'member_count', 'last_message_at', 'created_at', 'updated_at']

    def get_chat_type(self, obj):
        count = obj.memberships.filter(deleted_at__isnull=True).count()
        return 'group' if count > 1 else 'individual'

    def get_member_count(self, obj):
        return obj.memberships.filter(deleted_at__isnull=True).count()


class CreateChatSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, min_length=1)
    system_prompt = serializers.CharField(max_length=10000, required=False, allow_null=True, default=None)
    response_style = serializers.CharField(max_length=10000, required=False, allow_null=True, default=None)
    member_ids = serializers.ListField(child=serializers.IntegerField(), default=list)


class UpdateChatSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    system_prompt = serializers.CharField(max_length=10000, required=False, allow_null=True)
    response_style = serializers.CharField(max_length=10000, required=False, allow_null=True)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'chat_id', 'message', 'sender_type', 'created_by', 'created_at', 'deleted_at']


class SendMessageSerializer(serializers.Serializer):
    message = serializers.CharField(min_length=1, max_length=100000)
    sender_type = serializers.ChoiceField(choices=['user', 'system'], default='user')
