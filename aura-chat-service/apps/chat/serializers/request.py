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
    )


class CreateChatRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    system_prompt = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    response_style = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True,
        default=list,
    )
    is_ephemeral = serializers.BooleanField(required=False, default=False)

    def validate_tags(self, value: list[str]) -> list[str]:
        return _normalize_tags(value)


class MuteChatRequest(serializers.Serializer):
    muted_until = serializers.DateTimeField()


class UpdateChatRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    system_prompt = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    response_style = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        allow_empty=True,
    )
    is_ephemeral = serializers.BooleanField(required=False)

    def validate_tags(self, value: list[str]) -> list[str]:
        return _normalize_tags(value)
