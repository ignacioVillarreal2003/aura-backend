from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.classification_levels.serializers.response import ClassificationLevelResponse
from apps.compartments.serializers.response import CompartmentResponse
from apps.document_collections.models import DocumentCollection


@extend_schema_serializer(
    component_name="DocumentCollection",
    description=(
        "Hydrated projection of document_collection rows including catalogue expansions (`classification_level`, "
        "`compartments`) so clients avoid N+1 fetches across MAC metadata."
    ),
)
class DocumentCollectionResponse(serializers.ModelSerializer):
    classification_level = ClassificationLevelResponse(read_only=True)
    compartments = CompartmentResponse(many=True, read_only=True)

    class Meta:
        model = DocumentCollection
        fields = [
            "id",
            "name",
            "classification_level",
            "compartments",
            "created_by",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "id": {"help_text": "Primary surrogate key for the persisted collection row."},
            "name": {"help_text": "Displayed collection label."},
            "created_by": {
                "help_text": ("User id persisted at insertion time referencing the initiating principal."),
            },
            "created_at": {"help_text": "UTC insertion timestamp emitted from audit mixin."},
            "updated_at": {
                "help_text": ("UTC mutation timestamp emitted from audit mixin; null until first update."),
            },
        }
