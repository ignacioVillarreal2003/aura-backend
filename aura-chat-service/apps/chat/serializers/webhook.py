from rest_framework import serializers

from apps.chat.models.webhook import WEBHOOK_EVENTS, ChatWebhook


class WebhookCreateRequest(serializers.Serializer):
    url = serializers.URLField(help_text="HTTPS endpoint to receive signed webhook deliveries.")
    events = serializers.ListField(
        child=serializers.ChoiceField(choices=WEBHOOK_EVENTS),
        min_length=1,
        help_text="Non-empty list of event types (deduplicated). See enum in schema.",
    )

    def validate_events(self, value):
        return list(dict.fromkeys(value))


class WebhookUpdateRequest(serializers.Serializer):
    url = serializers.URLField(required=False)
    events = serializers.ListField(
        child=serializers.ChoiceField(choices=WEBHOOK_EVENTS),
        required=False,
        min_length=1,
        help_text="When set, replaces event subscription list.",
    )
    is_active = serializers.BooleanField(
        required=False,
        help_text="Disable delivery without deleting the webhook.",
    )

    def validate_events(self, value):
        return list(dict.fromkeys(value))


class WebhookResponse(serializers.ModelSerializer):
    class Meta:
        model = ChatWebhook
        fields = ["id", "chat_id", "url", "events", "is_active", "created_by", "created_at"]
