from rest_framework import serializers

_SYSTEM_PROMPT_MAX = 8000
_RESPONSE_STYLE_MAX = 2000


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
        max_length=_SYSTEM_PROMPT_MAX,
        help_text="Optional system prompt for the assistant.",
    )
    response_style = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=_RESPONSE_STYLE_MAX,
        help_text="Optional style instructions for assistant replies.",
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True,
        default=list,
        help_text="Up to 20 unique tags; each max 50 characters.",
    )
    def validate_tags(self, value: list[str]) -> list[str]:
        return _normalize_tags(value)


class UpdateChatRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    system_prompt = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=_SYSTEM_PROMPT_MAX,
    )
    response_style = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=_RESPONSE_STYLE_MAX,
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True,
        help_text="Replaces tag set when provided (normalized server-side).",
    )

    def validate_tags(self, value: list[str]) -> list[str]:
        return _normalize_tags(value)

    def validate(self, data):
        if not data:
            raise serializers.ValidationError("At least one field is required.")
        return data
