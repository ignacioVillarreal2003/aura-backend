from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers


@extend_schema_serializer(
    description=(
        "Insert a labelled MAC tier with deterministic ordering via `rank` (bounded to signed 16-bit positives). "
        "Server rejects duplicate lexical/ranking combinations."
    )
)
class CreateClassificationLevelRequest(serializers.Serializer):
    name = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
        help_text="Operational label surfaced in tooling; trims surrounding whitespace.",
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text="Optional description of the classification level.",
    )
    rank = serializers.IntegerField(
        min_value=1,
        max_value=32767,
        help_text=(
            "Strict ordering weight—lower ranks are often treated as baseline sensitivity; choose carefully when "
            "seeding hierarchies."
        ),
    )

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Name must not be empty or whitespace only.")
        return cleaned


@extend_schema_serializer(
    description=(
        "PATCH semantics for tweaking either display name or rank without replacing the entity wholesale. Provide "
        "at least one mutable field."
    )
)
class PatchClassificationLevelRequest(serializers.Serializer):
    name = serializers.CharField(max_length=100, trim_whitespace=True, required=False, help_text="Optional rename.")
    description = serializers.CharField(required=False, allow_blank=True, help_text="Optional description update.")
    rank = serializers.IntegerField(
        min_value=1,
        max_value=32767,
        required=False,
        help_text=(
            "Optional rerank—watch for downstream clearance implications when lowering numbers that previously "
            "denoted dominance."
        ),
    )

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Name must not be empty or whitespace only.")
        return cleaned

    def validate(self, data: dict) -> dict:
        if not data:
            raise serializers.ValidationError("At least one field must be provided.")
        return data
