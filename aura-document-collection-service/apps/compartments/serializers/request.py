from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers


@extend_schema_serializer(
    description=(
        "Introduce another need-to-know silo orthogonal to clearance rank—collections may span multiple compartments "
        "while audits track actor provenance separately."
    )
)
class CreateCompartmentRequest(serializers.Serializer):
    name = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
        help_text="Mandatory short handle; trims whitespace.",
    )
    description = serializers.CharField(
        allow_blank=True,
        default="",
        trim_whitespace=True,
        help_text=(
            "Optional explanatory blurb persisted verbatim (blank allowed)—useful for operators mapping legal "
            "program codes."
        ),
    )

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Name must not be empty or whitespace only.")
        return cleaned


@extend_schema_serializer(
    description="Sparse PATCH for compartments—send whichever subset of textual fields ought to mutate.",
)
class PatchCompartmentRequest(serializers.Serializer):
    name = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
        required=False,
        help_text="Optional renaming; trims whitespace.",
    )
    description = serializers.CharField(
        allow_blank=True,
        trim_whitespace=True,
        required=False,
        help_text=(
            "Optional replacement description chunk—supply empty string intentionally to intentionally clear prose."
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
