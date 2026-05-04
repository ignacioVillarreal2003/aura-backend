from rest_framework import serializers

from apps.message.models.chat_message import ChatMessage


class MessageResponse(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "chat_id",
            "message",
            "sender_type",
            "created_by",
            "created_at",
        ]


class AssistantBlockSerializer(serializers.Serializer):
    question = serializers.CharField(allow_blank=True)
    answer = serializers.CharField(allow_blank=True)
    fragments = serializers.ListField(child=serializers.DictField(), default=list)


class AssistantErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class SendMessagePostResponseSerializer(serializers.Serializer):
    message = MessageResponse()
    transcript = serializers.CharField(allow_null=True, required=False)
    assistant = AssistantBlockSerializer(allow_null=True, required=False)
    assistant_error = AssistantErrorSerializer(allow_null=True, required=False)
