from rest_framework import serializers

from apps.classification_levels.serializers.response import ClassificationLevelResponse
from apps.compartments.serializers.response import CompartmentResponse
from apps.document_collections.models import DocumentCollection


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
