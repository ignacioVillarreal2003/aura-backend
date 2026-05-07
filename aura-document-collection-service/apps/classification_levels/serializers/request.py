from rest_framework import serializers


class CreateClassificationLevelRequest(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True)
    rank = serializers.IntegerField(min_value=1, max_value=32767)

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Name must not be empty or whitespace only.")
        return cleaned


class PatchClassificationLevelRequest(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True, required=False)
    rank = serializers.IntegerField(min_value=1, max_value=32767, required=False)

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Name must not be empty or whitespace only.")
        return cleaned

    def validate(self, data: dict) -> dict:
        if not data:
            raise serializers.ValidationError("At least one field must be provided.")
        return data
