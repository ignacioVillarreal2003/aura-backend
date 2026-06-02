from rest_framework import serializers


class FeedbackSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField(help_text="Total feedback entries in the window.")
    thumbs_up = serializers.IntegerField()
    thumbs_down = serializers.IntegerField()
    satisfaction_rate = serializers.FloatField(
        allow_null=True,
        help_text="thumbs_up / (thumbs_up + thumbs_down), or null when there is no feedback.",
    )


class FeedbackAssistantRowSerializer(serializers.Serializer):
    assistant_id = serializers.IntegerField(allow_null=True)
    assistant_name = serializers.CharField()
    total = serializers.IntegerField()
    thumbs_up = serializers.IntegerField()
    thumbs_down = serializers.IntegerField()
    satisfaction_rate = serializers.FloatField(allow_null=True)


class FeedbackReasonRowSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_null=True, help_text="Reason code, or null if unspecified.")
    count = serializers.IntegerField()


class FeedbackNegativeRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    message_id = serializers.IntegerField()
    assistant_id = serializers.IntegerField(allow_null=True)
    assistant_name = serializers.CharField()
    reason = serializers.CharField(allow_null=True)
    comment = serializers.CharField(allow_null=True)
    user_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    message_excerpt = serializers.CharField(allow_blank=True)


class FeedbackAnalyticsResponse(serializers.Serializer):
    window_days = serializers.IntegerField()
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    summary = FeedbackSummarySerializer()
    assistants = FeedbackAssistantRowSerializer(many=True)
    reasons = FeedbackReasonRowSerializer(many=True)
    recent_negative = FeedbackNegativeRowSerializer(many=True)
