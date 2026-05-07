from rest_framework import serializers

from apps.compartments.models import Compartment


class CompartmentResponse(serializers.ModelSerializer):
    class Meta:
        model = Compartment
        fields = ["id", "name", "description"]
