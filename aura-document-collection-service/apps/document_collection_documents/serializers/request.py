from rest_framework import serializers


class AddDocumentToDocumentCollectionRequest(serializers.Serializer):
    document_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
