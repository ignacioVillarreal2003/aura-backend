from django.utils import timezone
from rest_framework import serializers


def _normalize_tags(value: list[str]) -> list[str]:
    seen = set()
    result = []
    for tag in value:
        t = tag.strip()
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    if len(result) > 20:
        raise serializers.ValidationError("Maximum 20 tags allowed.")
    return result


class BulkChatIdsRequest(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=100,
        help_text="Chat primary keys to include in the bulk operation (max 100).",
    )


class CreateChatRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255, help_text="Display name of the chat.")
    system_prompt = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional system prompt for the assistant.",
    )
    response_style = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional style instructions for assistant replies.",
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True,
        default=list,
        help_text="Up to 20 unique tags; each max 50 characters.",
    )
    is_ephemeral = serializers.BooleanField(
        required=False,
        default=False,
        help_text="If true, uses the ephemeral message / AI flow (no long-lived history per business rules).",
    )

    def validate_tags(self, value: list[str]) -> list[str]:
        return _normalize_tags(value)


class MuteChatRequest(serializers.Serializer):
    muted_until = serializers.DateTimeField(
        help_text="UTC datetime after which the chat is no longer muted for this user.",
    )

    def validate_muted_until(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("muted_until must be in the future.")
        return value


class UpdateChatRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    system_prompt = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    response_style = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True,
        help_text="Replaces tag set when provided (normalized server-side).",
    )
    def validate_tags(self, value: list[str]) -> list[str]:
        return _normalize_tags(value)
