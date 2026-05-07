from rest_framework import serializers

from apps.message.models.chat_message import ChatMessage
from apps.message.models.message_feedback import MessageFeedback
from apps.message.models.message_thread_reply import MessageThreadReply
from apps.message.models.pinned_message import PinnedMessage


class MessageResponse(serializers.ModelSerializer):
    is_bookmarked = serializers.SerializerMethodField()
    user_feedback = serializers.SerializerMethodField()
    thread_reply_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "chat_id",
            "message",
            "sender_type",
            "created_by",
            "created_at",
            "is_bookmarked",
            "user_feedback",
            "thread_reply_count",
        ]

    def get_is_bookmarked(self, obj) -> bool:
        return getattr(obj, "is_bookmarked", False) or False

    def get_user_feedback(self, obj):
        return getattr(obj, "user_feedback", None)

    def get_thread_reply_count(self, obj) -> int:
        return getattr(obj, "thread_reply_count", 0) or 0


class ThreadReplyResponse(serializers.ModelSerializer):
    class Meta:
        model = MessageThreadReply
        fields = ["id", "parent_message_id", "message", "created_by", "created_at"]


class FeedbackResponse(serializers.ModelSerializer):
    class Meta:
        model = MessageFeedback
        fields = ["id", "message_id", "user_id", "value", "created_at", "updated_at"]


class PinnedMessageResponse(serializers.ModelSerializer):
    message = MessageResponse(read_only=True)

    class Meta:
        model = PinnedMessage
        fields = ["id", "chat_id", "message_id", "pinned_by", "pinned_at", "message"]


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
