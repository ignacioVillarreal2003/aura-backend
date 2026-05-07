from rest_framework import serializers


def _normalize_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise serializers.ValidationError("Name must not be empty or whitespace only.")
    if len(cleaned) > 255:
        raise serializers.ValidationError("Name must be at most 255 characters after trimming.")
    return cleaned


class CreateDocumentCollectionRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255, trim_whitespace=True)
    classification_level_id = serializers.IntegerField(min_value=1)
    compartment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )

    def validate_name(self, value: str) -> str:
        return _normalize_name(value)


class PatchDocumentCollectionRequest(serializers.Serializer):
    name = serializers.CharField(max_length=255, trim_whitespace=True, required=False)
    classification_level_id = serializers.IntegerField(min_value=1, required=False)
    compartment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        required=False,
    )

    def validate_name(self, value: str) -> str:
        return _normalize_name(value)

    def validate(self, data: dict) -> dict:
        if not data:
            raise serializers.ValidationError("At least one field must be provided.")
        return data
