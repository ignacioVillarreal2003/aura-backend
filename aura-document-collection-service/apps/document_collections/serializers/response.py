from rest_framework import serializers

from apps.document_collections.models import DocumentCollection


class DocumentCollectionResponse(serializers.ModelSerializer):
    class Meta:
        model = DocumentCollection
        fields = [
            "id",
            "name",
            "created_by",
            "created_at",
            "updated_at",
        ]
