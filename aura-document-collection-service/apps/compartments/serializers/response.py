from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.compartments.models import Compartment


@extend_schema_serializer(
    component_name="Compartment",
    description="Need-to-know bucket metadata referenced by collection pivot tables and user compartment grants.",
)
class CompartmentResponse(serializers.ModelSerializer):
    class Meta:
        model = Compartment
        fields = ["id", "name", "description"]
        extra_kwargs = {
            "id": {"help_text": "Surrogate key joining DocumentCollection compartments."},
            "name": {"help_text": "Canonical compartment moniker displayed to admins."},
            "description": {
                "help_text": ("Long-form operator notes—may be blank when only the mnemonic name matters."),
            },
        }
