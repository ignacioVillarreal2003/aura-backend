from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers


@extend_schema_serializer(
    description=(
        "Attaches (`links`) an existing persisted document surrogate key to the parent collection. "
        "The API never uploads binaries—supply only the authoritative document id serviced elsewhere."
    )
)
class AddDocumentToDocumentCollectionRequest(serializers.Serializer):
    document_id = serializers.IntegerField(
        min_value=1,
        max_value=2**63 - 1,
        help_text=(
            "Registry primary key referencing `document_collection_documents.Document`. Must not collide with "
            "another active membership for this collection (`duplicate_document_link` otherwise)."
        ),
    )
