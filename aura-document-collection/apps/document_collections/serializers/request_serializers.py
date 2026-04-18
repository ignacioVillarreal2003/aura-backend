from rest_framework import serializers


class CreateDocumentCollectionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)


class PatchDocumentCollectionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)


class AddUserToCollectionSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)


class AddDocumentToCollectionSerializer(serializers.Serializer):
    document_id = serializers.IntegerField(min_value=1)
