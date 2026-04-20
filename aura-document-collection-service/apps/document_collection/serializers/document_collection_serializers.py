from rest_framework import serializers

from apps.document_collection.integrations.user_profile_client import UserProfile
from apps.document_collection.models import (
    DocumentCollection,
    DocumentInDocumentCollection,
    UserInDocumentCollection,
)


def document_collection_to_dict(document_collection: DocumentCollection) -> dict:
    return {
        "id": document_collection.id,
        "name": document_collection.name,
        "created_by": document_collection.created_by,
        "created_at": document_collection.created_at,
        "updated_at": document_collection.updated_at,
    }


def user_membership_to_dict(row: UserInDocumentCollection, profile: UserProfile) -> dict:
    return {
        "id": row.id,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "user": {
            "id": profile.id,
            "email": profile.email,
            "username": profile.username,
        },
    }


def document_link_to_dict(row: DocumentInDocumentCollection) -> dict:
    doc = getattr(row, "document", None)
    document_payload = None
    if doc is not None:
        document_payload = {"id": doc.id, "title": doc.name}
    return {
        "id": row.id,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "document": document_payload,
    }


class UserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True)


class DocumentSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)


class DocumentCollectionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    created_by = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True, allow_null=True)


class UserInDocumentCollectionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    created_by = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    user = UserSummarySerializer(read_only=True)


class DocumentInDocumentCollectionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    created_by = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    document = DocumentSummarySerializer(read_only=True, allow_null=True)
