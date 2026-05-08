from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from apps.document_collection_documents.models import DocumentInDocumentCollection


class LinkedDocumentSnippetSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        help_text="Underlying document surrogate key (`document.id`).",
    )
    title = serializers.CharField(
        help_text="Readable moniker lifted from persisted `document.name`; exposed externally as title.",
    )


@extend_schema_serializer(
    component_name="DocumentInDocumentCollection",
    description=(
        "Join row bridging a document registry entry with a MAC collection (`document_in_document_collection`). "
        "Soft-delete aware—only active memberships appear via service queries."
    ),
)
class DocumentInDocumentCollectionResponse(serializers.ModelSerializer):
    document = serializers.SerializerMethodField()

    class Meta:
        model = DocumentInDocumentCollection
        fields = [
            "id",
            "created_by",
            "created_at",
            "document",
        ]
        extra_kwargs = {
            "id": {"help_text": "Surrogate identifier for this membership/link row."},
            "created_by": {"help_text": "Actor attaching the document to the collection."},
            "created_at": {"help_text": "UTC timestamp when linkage materialized."},
        }

    @extend_schema_field(LinkedDocumentSnippetSerializer(allow_null=True))
    def get_document(self, obj: DocumentInDocumentCollection) -> dict[str, Any] | None:
        doc = getattr(obj, "document", None)
        if doc is None:
            return None
        return {"id": doc.id, "title": doc.name}
