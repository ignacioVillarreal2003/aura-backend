from rest_framework import serializers

from apps.document_collections.models import (
    DocumentCollection,
    DocumentInDocumentCollection,
    UserInDocumentCollection,
)


def collection_to_dict(collection: DocumentCollection) -> dict:
    return {
        "id": collection.id,
        "name": collection.name,
        "created_by": collection.created_by,
        "created_at": collection.created_at,
        "updated_at": collection.updated_at,
    }


def user_membership_to_dict(row: UserInDocumentCollection) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


def document_link_to_dict(row: DocumentInDocumentCollection) -> dict:
    return {
        "id": row.id,
        "document_id": row.document_id,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


class DocumentCollectionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    created_by = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True, allow_null=True)


class UserInCollectionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    created_by = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class DocumentInCollectionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    document_id = serializers.IntegerField(read_only=True)
    created_by = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
