from rest_framework import serializers

from apps.chat.models.webhook import WEBHOOK_EVENTS, ChatWebhook


class WebhookCreateRequest(serializers.Serializer):
    url = serializers.URLField()
    events = serializers.ListField(
        child=serializers.ChoiceField(choices=WEBHOOK_EVENTS),
        min_length=1,
    )


class WebhookUpdateRequest(serializers.Serializer):
    url = serializers.URLField(required=False)
    events = serializers.ListField(
        child=serializers.ChoiceField(choices=WEBHOOK_EVENTS),
        required=False,
        min_length=1,
    )
    is_active = serializers.BooleanField(required=False)


class WebhookResponse(serializers.ModelSerializer):
    class Meta:
        model = ChatWebhook
        fields = ["id", "chat_id", "url", "events", "is_active", "created_by", "created_at"]
