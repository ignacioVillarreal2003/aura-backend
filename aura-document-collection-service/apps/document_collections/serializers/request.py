from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers


def _normalize_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise serializers.ValidationError("Name must not be empty or whitespace only.")
    if len(cleaned) > 255:
        raise serializers.ValidationError("Name must be at most 255 characters after trimming.")
    return cleaned


@extend_schema_serializer(
    description=(
        "Create a MAC-aware grouping of documents requiring at least one compartment for need-to-know scoping "
        "and referencing an existing classification level id."
    )
)
class CreateDocumentCollectionRequest(serializers.Serializer):
    name = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
        help_text="Friendly label surfaced in UIs; trimmed and non-blank.",
    )
    classification_level_id = serializers.IntegerField(
        min_value=1,
        help_text=(
            "Foreign key to classification_levels.id indicating the maximal sensitivity ladder position "
            "associated with documents in this collection."
        ),
    )
    compartment_ids = serializers.ListField(
        child=serializers.IntegerField(
            min_value=1,
            help_text="Compartment surrogate key from compartments.id.",
        ),
        allow_empty=False,
        help_text=(
            "At least one compartment is mandatory at creation—the UI should never attempt to instantiate "
            "an empty cage. Duplicates collapse server-side prior to inserts."
        ),
    )

    def validate_name(self, value: str) -> str:
        return _normalize_name(value)


@extend_schema_serializer(
    description=(
        "Sparse update payload for PATCH operations. Omit fields you do not want to touch; compartment_ids replacements "
        "rewrite the pivot table wholesale when provided."
    )
)
class PatchDocumentCollectionRequest(serializers.Serializer):
    name = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
        required=False,
        help_text="When supplied, trims whitespace and forbids whitespace-only outcomes.",
    )
    classification_level_id = serializers.IntegerField(
        min_value=1,
        required=False,
        help_text=(
            "If present, swaps the FK to classification_levels entirely—ensure downstream ingestion tolerates reranking."
        ),
    )
    compartment_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        required=False,
        help_text=(
            "When sent, clears prior compartment memberships for the row and attaches the authoritative new set "
            "(still disallowing empties)."
        ),
    )

    def validate_name(self, value: str) -> str:
        return _normalize_name(value)

    def validate(self, data: dict) -> dict:
        if not data:
            raise serializers.ValidationError("At least one field must be provided.")
        return data
