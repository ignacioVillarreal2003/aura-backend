from rest_framework import serializers


class AddUserToDocumentCollectionRequest(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
