from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.document_collection_documents.models import DocumentInDocumentCollection


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

    def get_document(self, obj: DocumentInDocumentCollection) -> dict[str, Any] | None:
        doc = getattr(obj, "document", None)
        if doc is None:
            return None
        return {"id": doc.id, "title": doc.name}
