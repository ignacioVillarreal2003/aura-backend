from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.classification_levels.models import ClassificationLevel


@extend_schema_serializer(
    component_name="ClassificationLevel",
    description="Catalogued MAC ladder entry combining human-friendly naming with integer rank sequencing.",
)
class ClassificationLevelResponse(serializers.ModelSerializer):
    class Meta:
        model = ClassificationLevel
        fields = ["id", "name", "rank", "description"]
        extra_kwargs = {
            "id": {"help_text": "Primary key for FK references from collections/users."},
            "name": {"help_text": "Short label surfaced in approvals or policy editors."},
            "rank": {
                "help_text": (
                    "Relative ordering heuristic—consumers derive dominance by comparing ints rather than lexical names."
                ),
            },
        }
