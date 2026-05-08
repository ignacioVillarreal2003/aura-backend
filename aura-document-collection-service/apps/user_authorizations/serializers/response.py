from __future__ import annotations

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.classification_levels.serializers.response import ClassificationLevelResponse
from apps.compartments.serializers.response import CompartmentResponse
from apps.user_authorizations.models import UserClearance, UserCompartment


@extend_schema_serializer(
    component_name="UserClearance",
    description="Single-row clearance ledger mapping a user_id to the canonical classification level entity.",
)
class UserClearanceResponse(serializers.ModelSerializer):
    classification_level = ClassificationLevelResponse(read_only=True)

    class Meta:
        model = UserClearance
        fields = ["id", "user_id", "classification_level", "created_by", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Primary key for the clearance record."},
            "user_id": {"help_text": "Subject user receiving MAC ceiling assignment."},
            "created_by": {"help_text": "Actor id writing the clearance row."},
            "created_at": {"help_text": "UTC timestamp when clearance last materialized."},
        }


@extend_schema_serializer(
    component_name="UserCompartment",
    description="Join row representing compartment membership for a subject user with audit metadata.",
)
class UserCompartmentResponse(serializers.ModelSerializer):
    compartment = CompartmentResponse(read_only=True)

    class Meta:
        model = UserCompartment
        fields = ["id", "user_id", "compartment", "created_by", "created_at"]
        extra_kwargs = {
            "id": {"help_text": "Primary key for the membership row."},
            "user_id": {"help_text": "Subject user granted compartment access."},
            "created_by": {"help_text": "Actor id performing the grant."},
            "created_at": {"help_text": "UTC timestamp when membership became active."},
        }


@extend_schema_serializer(
    component_name="UserAuthorizationSnapshot",
    description=(
        "Aggregated MAC snapshot for a specific user_id: optional clearance plus every active compartment membership. "
        "Ideal for admin consoles before mutating linked resources."
    ),
)
class UserAuthorizationResponse(serializers.Serializer):
    user_id = serializers.IntegerField(
        help_text="Target subject mirrored from the URL path parameter.",
    )
    clearance = UserClearanceResponse(
        allow_null=True,
        help_text="Populated when clearance exists; null if the user has no recorded ceiling yet.",
    )
    compartments = UserCompartmentResponse(
        many=True,
        help_text="Zero-to-many compartment grants including nested compartment payload.",
    )
