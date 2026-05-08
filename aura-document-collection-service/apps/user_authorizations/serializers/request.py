from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers


@extend_schema_serializer(
    description=(
        "Upsert clearance for `{user}` path segment: ties the acting target to a validated classification_level_id. "
        "Repeated calls overwrite the single-row clearance ledger."
    )
)
class SetUserClearanceRequest(serializers.Serializer):
    classification_level_id = serializers.IntegerField(
        min_value=1,
        help_text=(
            "Foreign key referencing classification_levels.id that should cap the user's effective MAC ceiling going "
            "forward."
        ),
    )


@extend_schema_serializer(
    description=(
        "Creates a compartment membership join for `{user}` when not already assigned; duplicate attempts raise "
        "conflict responses."
    )
)
class AddUserCompartmentRequest(serializers.Serializer):
    compartment_id = serializers.IntegerField(
        min_value=1,
        help_text="Existing compartment surrogate key referencing compartments.id.",
    )
