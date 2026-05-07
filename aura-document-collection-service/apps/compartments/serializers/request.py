from rest_framework import serializers


class CreateCompartmentRequest(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True)
    description = serializers.CharField(allow_blank=True, default="", trim_whitespace=True)

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Name must not be empty or whitespace only.")
        return cleaned


class PatchCompartmentRequest(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True, required=False)
    description = serializers.CharField(allow_blank=True, trim_whitespace=True, required=False)

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Name must not be empty or whitespace only.")
        return cleaned

    def validate(self, data: dict) -> dict:
        if not data:
            raise serializers.ValidationError("At least one field must be provided.")
        return data
